"""SQLAlchemy database models."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from mcp_server.config import settings

Base = declarative_base()


class Tenant(Base):
    """Tenant model for multi-tenancy."""

    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    master_key_hash = Column(String(255), unique=True, nullable=False, index=True)
    salt = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Store(Base):
    """Store model for OrderDesk store configurations."""

    __tablename__ = "stores"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    store_id = Column(String(255), nullable=False)
    encrypted_api_key = Column(Text, nullable=False)
    label = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Store(id={self.id}, store_id={self.store_id}, label={self.label})>"


class AuditLog(Base):
    """Audit log for tracking tenant actions."""

    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    action = Column(String(255), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


class WebhookEvent(Base):
    """Webhook event storage for deduplication and processing."""

    __tablename__ = "webhook_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    payload = Column(Text, nullable=False)
    processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# Database engine and session (lazy initialization)
engine = None
SessionLocal = None

def get_engine():
    """Get the database engine."""
    global engine
    if engine is None:
        from mcp_server.config import settings
        engine = create_engine(
            settings.database_url,
            echo=False,  # Set to True for SQL debugging
            pool_pre_ping=True,
        )
    return engine

def get_session_local():
    """Get the session maker."""
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return SessionLocal


def create_tables() -> None:
    """Create all database tables."""
    Base.metadata.create_all(bind=get_engine())


def get_db():
    """Get database session."""
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()
