"""Input validation utilities."""

from typing import Optional


class ValidationError(Exception):
    """Custom validation error."""

    pass


def validate_message_length(message: str, max_length: int = 2000) -> None:
    """Validate message length."""
    if len(message) > max_length:
        raise ValidationError(f"Message exceeds maximum length of {max_length} characters")


def validate_message_content(message: str) -> None:
    """Validate message content."""
    if not message.strip():
        raise ValidationError("Message cannot be empty or whitespace only")

    # Check for excessive repetition (potential token bombing)
    words = message.split()
    if len(words) > 10:
        unique_words = set(words)
        repetition_ratio = len(words) / len(unique_words)
        if repetition_ratio > 25:
            raise ValidationError("Message contains excessive repetition")


def validate_message(message: str, max_length: int = 2000) -> str:
    """
    Validate and sanitize message.

    Returns:
        Sanitized message
    """
    validate_message_length(message, max_length)
    validate_message_content(message)

    # Sanitize
    message = message.strip()

    return message
