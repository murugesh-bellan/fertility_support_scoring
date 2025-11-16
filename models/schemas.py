"""Pydantic models for request/response validation."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ActionType(str, Enum):
    """Recommended action based on score."""

    EMERGENCY_ALERT = "emergency_alert"
    BOOK_GP_APPOINTMENT = "book_gp_appointment"
    NOTIFY_CARETAKER = "notify_caretaker"
    LOG_ONLY = "log_only"
    OUT_OF_DOMAIN = "out_of_domain"


class ScoreRequest(BaseModel):
    """Request model for scoring endpoint."""

    message: str = Field(..., min_length=1, max_length=2000, description="Message to score")

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Validate and sanitize message."""
        if not v.strip():
            raise ValueError("Message cannot be empty or whitespace only")
        return v.strip()


class ScoreResponse(BaseModel):
    """Response model for scoring endpoint."""

    score: int = Field(..., ge=-1, le=10, description="Emotional distress score")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the score")
    domain_match: bool = Field(..., description="Whether message is in domain")
    reasoning: str = Field(..., description="Explanation for the score")
    key_indicators: list[str] = Field(default_factory=list, description="Key emotional indicators")
    recommended_action: ActionType = Field(..., description="Recommended intervention")
    action_rationale: str = Field(..., description="Why this action is recommended")
    trace_id: Optional[str] = Field(None, description="Request correlation ID")
    run_url: Optional[str] = Field(None, description="LangSmith trace URL")
    latency_ms: Optional[int] = Field(None, description="Processing latency in milliseconds")
    tokens_used: Optional[int] = Field(None, description="Total tokens used")
    injection_detected: bool = Field(default=False, description="Whether injection was detected")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    bedrock_available: bool
    cache_enabled: bool
    version: str = "0.1.0"
