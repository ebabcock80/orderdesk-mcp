"""Structured JSON logging configuration with correlation IDs and secret redaction."""

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog

from mcp_server.config import settings

# Context vars for request tracing and tenant context
correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')
tenant_id_var: ContextVar[str] = ContextVar('tenant_id', default='')
store_id_var: ContextVar[str] = ContextVar('store_id', default='')
tool_name_var: ContextVar[str] = ContextVar('tool_name', default='')


# Comprehensive list of sensitive fields to redact
REDACTED_FIELDS = {
    'master_key', 'api_key', 'api_key_ciphertext',
    'password', 'token', 'secret', 'authorization',
    'jwt_secret_key', 'session_token', 'csrf_token',
    'smtp_password', 'webhook_secret', 'mcp_kms_key',
    'sendgrid_api_key', 'postmark_server_token'
}


def redact_secrets(data: Any) -> Any:
    """
    Recursively redact sensitive fields from any data structure.

    Per specification: Never log plaintext secrets.
    """
    if isinstance(data, dict):
        return {
            k: '[REDACTED]' if k.lower() in REDACTED_FIELDS else redact_secrets(v)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [redact_secrets(item) for item in data]
    elif isinstance(data, str):
        # Redact long strings that might be secrets
        if len(data) > 50 and any(pattern in data.lower() for pattern in ['key', 'token', 'secret']):
            return data[:8] + '...[REDACTED]'
    return data


def add_correlation_id(logger, method_name, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Add correlation ID and context to log events."""
    event_dict['correlation_id'] = correlation_id_var.get() or str(uuid.uuid4())
    event_dict['tenant_id'] = tenant_id_var.get()
    event_dict['store_id'] = store_id_var.get()
    event_dict['tool_name'] = tool_name_var.get()
    return event_dict


def redact_sensitive_data(logger, method_name, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive data from logs."""
    return redact_secrets(event_dict)


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
        add_correlation_id,  # Add correlation ID and context
        redact_sensitive_data,  # Redact secrets
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
