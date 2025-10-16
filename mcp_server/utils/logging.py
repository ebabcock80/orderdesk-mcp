"""Structured JSON logging configuration."""

import json
import logging
import sys
from typing import Any, Dict

import structlog

from mcp_server.config import settings


def redact_sensitive_data(logger, method_name, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive data from logs."""
    # Redact API keys and master keys
    for key, value in event_dict.items():
        if isinstance(value, str):
            if "api_key" in key.lower() or "master_key" in key.lower():
                event_dict[key] = "***REDACTED***"
            elif len(value) > 50 and any(pattern in value.lower() for pattern in ["key", "token", "secret"]):
                event_dict[key] = value[:10] + "***REDACTED***"
    return event_dict


def setup_logging():
    """Configure structured JSON logging."""
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )

    # Configure structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        redact_sensitive_data,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger()


# Global logger instance
logger = setup_logging()
