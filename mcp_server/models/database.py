"""
SQLAlchemy database models for OrderDesk MCP Server.

Per specification:
- Tenants: Master key hashes (never plaintext)
- Stores: Encrypted API keys (AES-256-GCM with separate ciphertext, tag, nonce)
- Sessions: WebUI JWT sessions (if ENABLE_WEBUI=true)
- MagicLinks: Signup/login tokens (if ENABLE_WEBUI=true)
- MasterKeyMetadata: Key rotation tracking (if ENABLE_WEBUI=true)
- AuditLog: Security audit trail
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# Database base class (SQLAlchemy 2.0 style)
class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# Enable foreign key support for SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign key constraints in SQLite."""
    if hasattr(dbapi_conn, "execute"):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# ============================================================================
# Core Tables (Always Created)
# ============================================================================


class Tenant(Base):
    """
    Tenant model for multi-tenancy.

    One tenant = one master key = many stores.
    Per specification: Store only salted master key hashes (never plaintext).
    """

    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    master_key_hash = Column(String(255), nullable=False)  # bcrypt hash
    salt = Column(String(255), nullable=False)  # Random salt for HKDF

    # Phase 6: Optional email for public signup
    email = Column(String(255), nullable=True, unique=True)  # Optional, for signup
    email_verified = Column(Boolean, default=False, nullable=False)

    # Activity tracking for user management
    last_login = Column(DateTime, nullable=True)
    last_activity = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=True,
    )

    __table_args__ = (
        Index("idx_tenants_master_key_hash", "master_key_hash"),
        Index("idx_tenants_email", "email"),
    )


class Store(Base):
    """
    Store model for OrderDesk store configurations.

    Per specification: API keys encrypted with AES-256-GCM.
    Stores ciphertext, tag, and nonce separately for proper GCM authentication.
    """

    __tablename__ = "stores"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(
        String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    store_id = Column(String(255), nullable=False)  # OrderDesk store ID
    store_name = Column(String(255), nullable=False)  # Friendly name for lookup
    label = Column(String(255), nullable=True)  # Optional label

    # AES-256-GCM encrypted API key (separate components)
    api_key_ciphertext = Column(Text, nullable=False)  # Base64-encoded ciphertext
    api_key_tag = Column(String(255), nullable=False)  # Base64-encoded GCM tag
    api_key_nonce = Column(String(255), nullable=False)  # Base64-encoded nonce/IV

    # Cached OrderDesk store configuration (fetched from /api/v2/store)
    store_config = Column(
        Text, nullable=True
    )  # JSON: {folders: {id: name}, settings: {...}}
    config_fetched_at = Column(DateTime, nullable=True)  # Last time config was fetched

    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        Index("idx_stores_tenant_id", "tenant_id"),
        Index("idx_stores_store_name", "tenant_id", "store_name"),
        UniqueConstraint("tenant_id", "store_name", name="uq_tenant_store_name"),
        UniqueConstraint("tenant_id", "store_id", name="uq_tenant_store_id"),
    )

    def __repr__(self) -> str:
        return f"<Store(id={self.id}, store_id={self.store_id}, store_name={self.store_name}, label={self.label})>"


class AuditLog(Base):
    """
    Audit log for tracking all tool calls and admin actions.

    Per specification: Log all MCP and WebUI operations with full context.
    Used by trace viewer in WebUI.
    """

    __tablename__ = "audit_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(
        String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    store_id = Column(String, nullable=True)  # Nullable if tenant-level action
    tool_name = Column(String(255), nullable=False)  # MCP tool name or action
    parameters = Column(Text, nullable=True)  # JSON (secrets redacted)
    status = Column(String(50), nullable=False)  # 'success' or 'error'
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    request_id = Column(String(255), nullable=False)  # Correlation ID
    source = Column(String(50), nullable=False)  # 'mcp' or 'webui'
    ip_address = Column(String(255), nullable=True)  # Client IP (WebUI only)
    user_agent = Column(Text, nullable=True)  # Browser UA (WebUI only)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        Index("idx_audit_log_tenant_id", "tenant_id"),
        Index("idx_audit_log_created_at", "created_at"),
        Index("idx_audit_log_request_id", "request_id"),
        Index("idx_audit_log_source", "source"),
        Index("idx_audit_log_status", "status"),
    )


# ============================================================================
# WebUI Tables (Created if ENABLE_WEBUI=true)
# ============================================================================


class Session(Base):
    """
    WebUI session management.

    Stores JWT sessions for web interface authentication.
    Per Q17: Cookie + database session record (revocable).
    """

    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(
        String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    session_token = Column(
        String(255), nullable=False, unique=True
    )  # JWT or session ID
    ip_address = Column(String(255), nullable=True)
    user_agent = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    last_activity_at = Column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        Index("idx_sessions_tenant_id", "tenant_id"),
        Index("idx_sessions_token", "session_token"),
        Index("idx_sessions_expires_at", "expires_at"),
    )


class MagicLink(Base):
    """
    Magic link tokens for passwordless signup/login.

    Per specification: 15-minute expiry, one-time use, hashed storage.
    """

    __tablename__ = "magic_links"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), nullable=False)
    token = Column(String(255), nullable=False)  # Secure random token
    token_hash = Column(String(255), nullable=False, unique=True)  # SHA-256 hash
    purpose = Column(String(50), nullable=False)  # 'signup' or 'login'
    tenant_id = Column(
        String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True
    )  # NULL for signup
    ip_address = Column(String(255), nullable=True)
    used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        Index("idx_magic_links_email", "email"),
        Index("idx_magic_links_token_hash", "token_hash"),
        Index("idx_magic_links_expires_at", "expires_at"),
        Index("idx_magic_links_purpose", "purpose"),
    )


class MasterKeyMetadata(Base):
    """
    Master key metadata for rotation and identification.

    Per specification: Store prefix only (first 8 chars), never full key.
    Supports key rotation with grace periods (Q8: 7 days).
    """

    __tablename__ = "master_key_metadata"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(
        String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    master_key_prefix = Column(
        String(16), nullable=False
    )  # First 8 chars for identification
    label = Column(
        String(255), nullable=True
    )  # User-provided label (e.g., "Production Key")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_master_key_metadata_tenant_id", "tenant_id"),
        Index("idx_master_key_metadata_revoked", "revoked"),
    )


class WebhookEvent(Base):
    """Webhook event storage for deduplication and processing."""

    __tablename__ = "webhook_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    payload = Column(Text, nullable=False)
    processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


# ============================================================================
# Database Engine and Session Management
# ============================================================================

engine = None
SessionLocal = None


def get_engine():
    """
    Get the SQLAlchemy database engine (lazy initialization).

    Configured with:
    - pool_pre_ping: Verify connections before using
    - echo: SQL logging (disabled by default)
    """
    global engine
    if engine is None:
        from mcp_server.config import settings
        from mcp_server.utils.logging import logger

        logger.info(
            "Initializing database engine",
            database_url=settings.database_url.split("://")[0] + "://...",
        )

        engine = create_engine(
            settings.database_url,
            echo=False,  # Set to True for SQL debugging
            pool_pre_ping=True,
            pool_recycle=3600,  # Recycle connections after 1 hour
        )
    return engine


def get_session_local():
    """Get the SQLAlchemy session maker."""
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=get_engine()
        )
    return SessionLocal


def init_db() -> None:
    """
    Initialize database: create all tables.

    Per specification:
    - Core tables always created: Tenant, Store, AuditLog
    - WebUI tables created if ENABLE_WEBUI=true: Session, MagicLink, MasterKeyMetadata
    """
    from mcp_server.utils.logging import logger

    logger.info("Initializing database schema")

    # Create all tables (WebUI tables will be created but unused if ENABLE_WEBUI=false)
    Base.metadata.create_all(bind=get_engine())

    logger.info(
        "Database initialized",
        tables_created=[
            "tenants",
            "stores",
            "audit_log",
            "webhook_events",
            "sessions",
            "magic_links",
            "master_key_metadata",
        ],
    )


def create_tables() -> None:
    """Alias for init_db() for backward compatibility."""
    init_db()


def get_db():
    """
    Get database session for dependency injection.

    Usage:
        @app.get("/endpoint")
        async def endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()
