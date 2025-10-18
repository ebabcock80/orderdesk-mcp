"""Configuration management using Pydantic settings."""

import base64

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # =========================================================================
    # Server Configuration
    # =========================================================================
    port: int = Field(
        default=8080, ge=1024, le=65535, description="Port to bind the server to"
    )
    trust_proxy: bool = Field(
        default=False,
        description="Trust proxy headers (X-Forwarded-For, CF-Connecting-IP)",
    )
    log_level: str = Field(default="INFO", description="Logging level")

    # Security
    mcp_kms_key: str = Field(..., description="32+ byte base64 encoded encryption key")
    server_admin_token: str | None = Field(
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
    webhook_secret: str | None = Field(
        default=None, description="Optional webhook secret for validation"
    )

    # CORS
    allowed_origins: list[str] = Field(
        default_factory=list, description="Allowed CORS origins"
    )

    # Database
    database_url: str = Field(
        default="sqlite:///data/app.db", description="Database connection URL"
    )

    # =========================================================================
    # Cache Configuration
    # =========================================================================
    cache_ttl_orders: int = Field(
        default=15, description="Cache TTL for orders (seconds)"
    )
    cache_ttl_products: int = Field(
        default=60, description="Cache TTL for products (seconds)"
    )
    cache_ttl_customers: int = Field(
        default=60, description="Cache TTL for customers (seconds)"
    )
    cache_ttl_store_settings: int = Field(
        default=300, description="Cache TTL for store settings (seconds)"
    )

    # =========================================================================
    # Resilience Configuration
    # =========================================================================
    http_timeout: int = Field(default=30, description="HTTP client timeout (seconds)")
    http_max_retries: int = Field(
        default=3, description="Max retries for HTTP 429/5xx errors"
    )
    mutation_max_retries: int = Field(
        default=5, description="Max retries for mutation conflicts"
    )

    # =========================================================================
    # WebUI Configuration (Optional - disabled by default)
    # =========================================================================
    enable_webui: bool = Field(
        default=False, description="Enable optional web interface"
    )

    # WebUI Authentication
    jwt_secret_key: str | None = Field(
        default=None, description="JWT signing key (required if enable_webui=true)"
    )
    session_timeout: int = Field(
        default=86400, description="Session timeout in seconds (24 hours)"
    )

    # Session Cookie Configuration
    session_cookie_name: str = Field(
        default="orderdesk_session", description="Session cookie name"
    )
    session_cookie_secure: bool = Field(
        default=True, description="Require HTTPS for cookies"
    )
    session_cookie_httponly: bool = Field(
        default=True, description="HttpOnly flag for cookies"
    )
    session_cookie_samesite: str = Field(
        default="Strict", description="SameSite cookie attribute"
    )

    # Admin Master Key (Optional - for development/testing)
    admin_master_key: str | None = Field(
        default=None,
        description="Admin master key for guaranteed access (auto-provisions on startup)",
    )

    # MCP Client Configuration
    public_url: str = Field(
        default="http://localhost:8080",
        description="Public URL for MCP client configuration (e.g., https://your-domain.com)",
    )

    # WebUI Rate Limiting
    webui_rate_limit_login: int = Field(
        default=5, description="Login attempts per IP per minute"
    )
    webui_rate_limit_signup: int = Field(
        default=2, description="Signup attempts per IP per minute"
    )
    webui_rate_limit_api_console: int = Field(
        default=30, description="API console requests per user per minute"
    )

    # CSRF Configuration
    csrf_secret_key: str | None = Field(
        default=None, description="CSRF token secret (auto-generated if omitted)"
    )

    # WebUI Features
    enable_trace_viewer: bool = Field(
        default=True, description="Enable trace/logs viewer in UI"
    )
    enable_audit_log: bool = Field(default=True, description="Enable audit logging")
    audit_log_retention_days: int = Field(
        default=90, description="Audit log retention period (days)"
    )

    # =========================================================================
    # Email Configuration (Phase 6)
    # =========================================================================
    enable_public_signup: bool = Field(
        default=False, description="Enable public signup with email verification"
    )
    require_email_verification: bool = Field(
        default=True, description="Require email verification for signup"
    )

    # SMTP Settings
    smtp_host: str | None = Field(default=None, description="SMTP server hostname")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_username: str | None = Field(default=None, description="SMTP username")
    smtp_password: str | None = Field(default=None, description="SMTP password")
    smtp_use_tls: bool = Field(default=True, description="Use TLS for SMTP")
    smtp_from_email: str | None = Field(
        default=None, description="Default sender email address"
    )

    # Email Provider
    email_provider: str = Field(
        default="console",
        description="Email provider (smtp, console)",
    )

    # Signup Rate Limiting
    signup_rate_limit_per_hour: int = Field(
        default=3, description="Max signups per IP per hour"
    )
    signup_verification_expiry: int = Field(
        default=900, description="Email verification expiry (seconds, default 15 min)"
    )

    # =========================================================================
    # Testing Configuration
    # =========================================================================
    orderdesk_test_enabled: bool = Field(
        default=False, description="Enable integration tests"
    )
    orderdesk_test_store_id: str | None = Field(
        default=None, description="Test store ID for integration tests"
    )
    orderdesk_test_api_key: str | None = Field(
        default=None, description="Test API key for integration tests"
    )

    # =========================================================================
    # Advanced Configuration
    # =========================================================================
    enable_metrics: bool = Field(
        default=True, description="Enable Prometheus metrics endpoint"
    )
    enable_detailed_health: bool = Field(
        default=True, description="Enable detailed health check endpoint"
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
    def parse_allowed_origins(cls, v: str) -> list[str]:
        """Parse comma-separated allowed origins."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v  # type: ignore[unreachable]

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

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str | None, info) -> str | None:
        """Validate JWT secret is provided when WebUI is enabled."""
        enable_webui = info.data.get("enable_webui", False)
        if enable_webui and not v:
            raise ValueError("JWT_SECRET_KEY is required when ENABLE_WEBUI=true")
        return v

    @field_validator("session_cookie_samesite")
    @classmethod
    def validate_samesite(cls, v: str) -> str:
        """Validate SameSite cookie attribute."""
        valid_values = ["Strict", "Lax", "None"]
        if v not in valid_values:
            raise ValueError(f"session_cookie_samesite must be one of: {valid_values}")
        return v


# Global settings instance (loads from environment variables)
settings = Settings()  # type: ignore[call-arg]
