"""Configuration management using Pydantic settings."""

import base64
import os
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server Configuration
    port: int = Field(default=8080, description="Port to bind the server to")
    trust_proxy: bool = Field(default=True, description="Trust proxy headers")
    log_level: str = Field(default="info", description="Logging level")

    # Security
    mcp_kms_key: str = Field(..., description="32+ byte base64 encoded encryption key")
    server_admin_token: Optional[str] = Field(
        default=None, description="Optional admin token for server management"
    )

    # Multi-tenancy
    auto_provision_tenant: bool = Field(
        default=True, description="Auto-create tenants for unknown master keys"
    )

    # Rate Limiting
    rate_limit_rpm: int = Field(
        default=120, description="Rate limit requests per minute"
    )

    # Caching
    cache_backend: str = Field(
        default="memory", description="Cache backend: memory, sqlite, redis"
    )
    redis_url: str = Field(
        default="redis://redis:6379/0", description="Redis connection URL"
    )

    # Webhooks
    webhook_secret: Optional[str] = Field(
        default=None, description="Optional webhook secret for validation"
    )

    # CORS
    allowed_origins: List[str] = Field(
        default_factory=list, description="Allowed CORS origins"
    )

    # Database
    database_url: str = Field(
        default="sqlite:///data/app.db", description="Database connection URL"
    )

    # Testing
    orderdesk_test_store_id: Optional[str] = Field(
        default=None, description="Test store ID for integration tests"
    )
    orderdesk_test_api_key: Optional[str] = Field(
        default=None, description="Test API key for integration tests"
    )

    @field_validator("mcp_kms_key")
    @classmethod
    def validate_kms_key(cls, v: str) -> str:
        """Validate that the KMS key is properly base64 encoded and at least 32 bytes."""
        try:
            decoded = base64.urlsafe_b64decode(v)
            if len(decoded) < 32:
                raise ValueError("KMS key must be at least 32 bytes when decoded")
            return v
        except Exception as e:
            raise ValueError(f"Invalid KMS key format: {e}")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: str) -> List[str]:
        """Parse comma-separated allowed origins."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["debug", "info", "warning", "error", "critical"]
        if v.lower() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.lower()

    @field_validator("cache_backend")
    @classmethod
    def validate_cache_backend(cls, v: str) -> str:
        """Validate cache backend."""
        valid_backends = ["memory", "sqlite", "redis"]
        if v.lower() not in valid_backends:
            raise ValueError(f"Cache backend must be one of: {valid_backends}")
        return v.lower()

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
    }


# Global settings instance
settings = Settings()
