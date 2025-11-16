"""Structured logging configuration."""

import json
import logging
import sys
from datetime import datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """Format logs as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id

        if hasattr(record, "event"):
            log_data["event"] = record.event

        if hasattr(record, "data"):
            log_data["data"] = record.data

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    # Reduce noise from libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def log_event(logger: logging.Logger, event: str, data: dict[str, Any], level: str = "INFO") -> None:
    """Log a structured event."""
    extra = {"event": event, "data": data}

    if level == "INFO":
        logger.info(event, extra=extra)
    elif level == "WARNING":
        logger.warning(event, extra=extra)
    elif level == "ERROR":
        logger.error(event, extra=extra)
    elif level == "DEBUG":
        logger.debug(event, extra=extra)
