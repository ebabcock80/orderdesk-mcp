-- Migration: Initial Schema
-- Version: 001
-- Description: Base schema with all core tables
-- Applied: This is the baseline schema (already exists from app startup)
-- ============================================================================

-- This migration is for reference only
-- The initial schema is created automatically by SQLAlchemy on first startup

-- Tables created:
-- - tenants
-- - stores
-- - audit_log
-- - webhook_events
-- - sessions
-- - magic_links
-- - master_key_metadata

-- No changes needed for existing databases
SELECT 'Initial schema already exists' as message;

