-- Migration: Add Store Config Caching
-- Version: 002
-- Description: Example migration showing how to add columns
-- Applied: This was already applied in development (store_config, config_fetched_at)
-- ============================================================================

-- Add store_config column for caching OrderDesk configuration
ALTER TABLE stores ADD COLUMN store_config TEXT;

-- Add timestamp for cache invalidation
ALTER TABLE stores ADD COLUMN config_fetched_at TIMESTAMP;

-- Create index for faster config lookups
CREATE INDEX IF NOT EXISTS idx_stores_config_fetched 
ON stores(config_fetched_at) WHERE config_fetched_at IS NOT NULL;

-- Record migration
INSERT INTO schema_version (version, description, applied_by, rollback_sql)
VALUES (
    2,
    'Add store config caching fields',
    'migration_script',
    'ALTER TABLE stores DROP COLUMN store_config; ALTER TABLE stores DROP COLUMN config_fetched_at; DROP INDEX idx_stores_config_fetched;'
);

