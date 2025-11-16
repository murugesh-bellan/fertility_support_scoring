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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from langsmith import Client as LangSmithClient
from langsmith import uuid7
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
    environment: str = "production"
    version: str = "0.1.0"

    class Config:
        env_file = ".env"


# Initialize settings
settings = Settings()

# Setup logging
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

# Setup LangSmith if configured
langsmith_enabled = False
langsmith_client = None
if settings.langsmith_api_key and settings.langsmith_tracing:
    try:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
        langsmith_enabled = True
        langsmith_client = LangSmithClient(
            api_key=settings.langsmith_api_key,
            api_url=settings.langsmith_endpoint
        )
        logger.info(f"LangSmith tracing enabled for project: {settings.langsmith_project}")
    except Exception as e:
        logger.warning(f"Failed to initialize LangSmith tracing: {e}")
        langsmith_enabled = False
        langsmith_client = None
else:
    logger.info("LangSmith tracing disabled")

# Initialize FastAPI
app = FastAPI(
    title="Fertility Support Agent",
    description="Emotional distress scoring for fertility treatment patients",
    version="0.1.0",
)

# Configure CORS to allow dashboard access (only in dev environment)
if settings.environment == "dev":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("CORS middleware enabled for development environment")

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


def construct_langsmith_url(run_id: str, project: str, endpoint: str) -> str:
    """Construct LangSmith trace URL from run_id.

    Note: This constructs a best-effort URL. The actual URL format may vary
    based on your LangSmith organization settings.
    """
    # Try to construct URL - format may need adjustment based on your org
    # Common formats:
    # - https://smith.langchain.com/o/{org_id}/projects/p/{project}/r/{run_id}
    # - For direct access, you can also use: {endpoint}/runs/{run_id}

    # Use a simplified format that should work for most cases
    base_url = endpoint.rstrip("/")
    # This will link to the run page - users may need to select their org
    return f"{base_url}/projects/{project}/runs/{run_id}"


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

    # Generate UUID v7 for correlation and LangSmith run_id
    correlation_uuid = uuid7()
    correlation_id = str(correlation_uuid)
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

        # Prepare LangSmith config with proper structure
        langsmith_config = None
        if langsmith_enabled:
            langsmith_config = {
                "run_name": "score_message",
                "run_id": correlation_uuid,  # Use UUID object, not string
                "metadata": {
                    "user_id": settings.holistic_ai_team_id,
                    "model": settings.holistic_ai_model,
                    "version": settings.version,
                    "environment": settings.environment,
                    "request_id": correlation_id,
                    "message_hash": message_hash,
                    "injection_detected": is_injection,
                    "injection_patterns": patterns if is_injection else [],
                    "message_length": len(message),
                    "cache_enabled": settings.cache_enabled,
                },
                "tags": [
                    "fertility-support",
                    "emotional-scoring",
                    f"injection-{'detected' if is_injection else 'clean'}",
                ],
            }

        # Score the message with LangSmith metadata
        result = await agent.score_message(
            message,
            config=langsmith_config,
            langsmith_enabled=langsmith_enabled,
            run_id=correlation_id
        )

        # Update LangSmith run with dynamic tags from key_indicators
        if langsmith_enabled and langsmith_client and "key_indicators" in result:
            try:
                # Add key_indicators as tags to the run
                dynamic_tags = [
                    f"indicator:{indicator.lower().replace(' ', '-')}"
                    for indicator in result["key_indicators"]
                ]
                # Update the run with additional tags
                langsmith_client.update_run(
                    run_id=correlation_uuid,
                    tags=dynamic_tags
                )
            except Exception as e:
                logger.warning(f"Failed to update LangSmith run with dynamic tags: {e}")

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

        # Construct LangSmith trace URL if enabled
        run_url = None
        if langsmith_enabled and "run_id" in result:
            run_url = construct_langsmith_url(
                result["run_id"],
                settings.langsmith_project,
                settings.langsmith_endpoint
            )

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
            run_url=run_url,
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
