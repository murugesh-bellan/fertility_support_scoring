"""FastAPI server for emotional support scoring."""

import hashlib
import logging
import os
import time
import uuid
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import SecretStr
from pydantic_settings import BaseSettings
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from agent.graph import ScoringAgent
from models.bedrock import HolisticAIBedrockChat
from models.schemas import HealthResponse, ScoreRequest, ScoreResponse
from observability.logging import log_event, setup_logging
from observability.metrics import (
    cache_hit_rate,
    get_metrics,
    injection_attempts_total,
    scoring_cost_usd,
    scoring_errors_total,
    scoring_latency_seconds,
    scoring_requests_total,
    scoring_tokens_used,
)
from security.injection import detector
from security.validation import ValidationError, validate_message

# Load environment variables
load_dotenv()


class Settings(BaseSettings):
    """Application settings."""

    # HolisticAI Bedrock
    holistic_ai_team_id: str
    holistic_ai_api_token: str
    holistic_ai_api_endpoint: str = (
        "https://ctwa92wg1b.execute-api.us-east-1.amazonaws.com/prod/invoke"
    )
    holistic_ai_model: str = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

    # LangSmith
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "fertility-support-agent"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_tracing: bool = True

    # Application
    log_level: str = "INFO"
    cache_enabled: bool = True
    rate_limit_per_minute: int = 60
    max_message_length: int = 2000

    class Config:
        env_file = ".env"


# Initialize settings
settings = Settings()

# Setup logging
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

# Setup LangSmith if configured
if settings.langsmith_api_key and settings.langsmith_tracing:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint

# Initialize FastAPI
app = FastAPI(
    title="Fertility Support Agent",
    description="Emotional distress scoring for fertility treatment patients",
    version="0.1.0",
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Initialize LLM and agent
llm = HolisticAIBedrockChat(
    team_id=settings.holistic_ai_team_id,
    api_token=SecretStr(settings.holistic_ai_api_token),
    api_endpoint=settings.holistic_ai_api_endpoint,
    model=settings.holistic_ai_model,
    temperature=0.7,
    max_tokens=1024,
)

agent = ScoringAgent(llm)

# Simple in-memory cache
cache_hits = 0
cache_misses = 0


@lru_cache(maxsize=100)
def cached_score(message_hash: str, message: str) -> dict:
    """Cache scoring results by message hash."""
    # This is a placeholder - actual scoring happens in the endpoint
    # The cache is used to store results after scoring
    return {}


@app.post("/score", response_model=ScoreResponse)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def score_message(request: Request, score_request: ScoreRequest) -> ScoreResponse:
    """Score a message for emotional distress."""
    global cache_hits, cache_misses

    correlation_id = str(uuid.uuid4())
    start_time = time.time()

    try:
        # Validate message
        message = validate_message(score_request.message, settings.max_message_length)

        # Check for injection attempts
        is_injection, patterns = detector.detect(message)
        if is_injection:
            injection_attempts_total.inc()
            log_event(
                logger,
                "injection_detected",
                {
                    "correlation_id": correlation_id,
                    "patterns": patterns,
                    "message_preview": message[:100],
                },
                level="WARNING",
            )

        # Sanitize message
        message = detector.sanitize(message)

        # Check cache
        message_hash = hashlib.sha256(message.encode()).hexdigest()[:16]

        if settings.cache_enabled:
            # Try to get from cache (simplified - in production use Redis)
            # For now, we'll skip caching to keep it simple for hackathon
            cache_misses += 1
            pass

        # Score the message
        result = await agent.score_message(message)

        # Calculate metrics
        latency = time.time() - start_time
        scoring_latency_seconds.observe(latency)
        scoring_tokens_used.observe(result["tokens_used"])

        # Estimate cost (Claude 3.5 Sonnet pricing: ~$3/1M input, ~$15/1M output tokens)
        # Rough estimate: 50/50 split
        cost = (result["tokens_used"] / 1_000_000) * 9  # Average of input/output
        scoring_cost_usd.inc(cost)

        # Update cache hit rate
        total_requests = cache_hits + cache_misses
        if total_requests > 0:
            cache_hit_rate.set(cache_hits / total_requests)

        # Log event
        log_event(
            logger,
            "score_generated",
            {
                "correlation_id": correlation_id,
                "message_hash": message_hash,
                "score": result["score"],
                "confidence": result["confidence"],
                "action": result["recommended_action"].value,
                "latency_ms": int(latency * 1000),
                "tokens_used": result["tokens_used"],
                "cost_usd": cost,
                "injection_detected": is_injection,
            },
        )

        # Track request
        scoring_requests_total.labels(
            status="success",
            action=result["recommended_action"].value,
        ).inc()

        # Build response
        response = ScoreResponse(
            score=result["score"],
            confidence=result["confidence"],
            domain_match=result["domain_match"],
            reasoning=result["reasoning"],
            key_indicators=result["key_indicators"],
            recommended_action=result["recommended_action"],
            action_rationale=result["action_rationale"],
            trace_id=correlation_id,
            latency_ms=result["latency_ms"],
            tokens_used=result["tokens_used"],
            injection_detected=is_injection,
        )

        return response

    except ValidationError as e:
        scoring_errors_total.labels(error_type="validation").inc()
        log_event(
            logger,
            "validation_error",
            {"correlation_id": correlation_id, "error": str(e)},
            level="WARNING",
        )
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        scoring_errors_total.labels(error_type="internal").inc()
        log_event(
            logger,
            "internal_error",
            {"correlation_id": correlation_id, "error": str(e)},
            level="ERROR",
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    # Test Bedrock connectivity
    bedrock_available = True
    try:
        # Quick test call
        await llm.ainvoke([{"role": "user", "content": "test"}])
    except Exception:
        bedrock_available = False

    return HealthResponse(
        status="healthy" if bedrock_available else "degraded",
        bedrock_available=bedrock_available,
        cache_enabled=settings.cache_enabled,
    )


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    metrics_output, content_type = get_metrics()
    return Response(content=metrics_output, media_type=content_type)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Fertility Support Agent",
        "version": "0.1.0",
        "status": "running",
        "endpoints": {
            "score": "POST /score",
            "health": "GET /health",
            "metrics": "GET /metrics",
            "docs": "GET /docs",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
