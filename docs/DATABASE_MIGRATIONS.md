# Database Migrations Guide

Complete guide for managing database schema changes in production.

---

## Overview

The OrderDesk MCP Server uses a simple, manual migration system optimized for SQLite. This provides full control without external dependencies.

**Key Features:**
- ✅ Version tracking in `schema_version` table
- ✅ Automatic backup before each migration
- ✅ Integrity verification
- ✅ Rollback SQL stored for safety
- ✅ No external tools required
- ✅ Compatible with SQLAlchemy models

---

## Migration Commands

### Check Current Version
```bash
./scripts/migrations/migrate.sh
```

**Output:**
```
Database Migration Status
=========================
Database: ./data/app.db
Current Version: 2

Migration History:
2|Add store config caching fields|2025-10-18 12:00:00|admin
1|Initial schema|2025-10-17 10:00:00|system
```

### List Available Migrations
```bash
./scripts/migrations/migrate.sh --list
```

**Output:**
```
Available Migrations:
====================
  v001 - initial schema
  v002 - add store config
  v003 - add user roles
```

### Apply Migration
```bash
./scripts/migrations/migrate.sh --apply 003
```

**Process:**
1. Creates pre-migration backup
2. Verifies current version
3. Applies SQL changes
4. Records migration in schema_version
5. Verifies database integrity

---

## Creating Migrations

### Migration Template

Create file: `scripts/migrations/versions/NNN_description.sql`

```sql
-- Migration: [Human-readable title]
-- Version: [NNN]
-- Description: [What this does and why]
-- ============================================================================

-- Begin transaction (optional but recommended)
BEGIN TRANSACTION;

-- Your schema changes here
ALTER TABLE table_name ADD COLUMN new_column TEXT;

CREATE INDEX IF NOT EXISTS idx_table_column 
ON table_name(new_column);

-- Record migration
INSERT INTO schema_version (version, description, applied_by, rollback_sql)
VALUES (
    [NNN],
    '[Description]',
    'migration_script',
    '[SQL to undo changes]'
);

-- Commit transaction
COMMIT;
```

### Example Migrations

**Example 1: Add Column**
```sql
-- Migration: Add Email Notifications
-- Version: 004
-- ============================================================================

ALTER TABLE tenants ADD COLUMN email_notifications_enabled INTEGER DEFAULT 1;

CREATE INDEX idx_tenants_email_notifications 
ON tenants(email_notifications_enabled);

INSERT INTO schema_version (version, description, applied_by, rollback_sql)
VALUES (
    4,
    'Add email notification preferences',
    'migration_script',
    'ALTER TABLE tenants DROP COLUMN email_notifications_enabled; DROP INDEX idx_tenants_email_notifications;'
);
```

**Example 2: Create Table**
```sql
-- Migration: Add API Keys Table
-- Version: 005
-- ============================================================================

CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    permissions TEXT NOT NULL,  -- JSON array
    last_used_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_api_keys_tenant ON api_keys(tenant_id);
CREATE INDEX idx_api_keys_expires ON api_keys(expires_at);

INSERT INTO schema_version (version, description, applied_by, rollback_sql)
VALUES (
    5,
    'Add API keys table for programmatic access',
    'migration_script',
    'DROP TABLE api_keys;'
);
```

**Example 3: Data Migration**
```sql
-- Migration: Normalize Store Names
-- Version: 006
-- ============================================================================

-- Update existing data
UPDATE stores 
SET store_name = TRIM(LOWER(store_name))
WHERE store_name != TRIM(LOWER(store_name));

-- Add uniqueness constraint (requires new table in SQLite)
CREATE TABLE stores_new (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    store_id TEXT NOT NULL,
    store_name TEXT NOT NULL UNIQUE,  -- Now unique
    -- ... other columns ...
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- Copy data
INSERT INTO stores_new SELECT * FROM stores;

-- Replace table
DROP TABLE stores;
ALTER TABLE stores_new RENAME TO stores;

-- Recreate indexes
CREATE INDEX idx_stores_tenant ON stores(tenant_id);
CREATE INDEX idx_stores_store_id ON stores(store_id);

INSERT INTO schema_version (version, description, applied_by, rollback_sql)
VALUES (
    6,
    'Normalize store names and add uniqueness constraint',
    'migration_script',
    'Complex rollback - restore from backup'
);
```

---

## Migration Workflow

### Development

```bash
# 1. Create migration file
nano scripts/migrations/versions/007_new_feature.sql

# 2. Test on development database
export DB_FILE=app_dev.db
./scripts/migrations/migrate.sh --apply 007

# 3. Verify changes
sqlite3 data/app_dev.db ".schema"

# 4. Commit migration file
git add scripts/migrations/versions/007_new_feature.sql
git commit -m "feat(db): add migration 007 - new feature"
```

### Staging

```bash
# 1. Pull latest migrations
git pull origin main

# 2. Review migrations
./scripts/migrations/migrate.sh --list

# 3. Backup database
./scripts/backup/backup.sh --docker --compress

# 4. Apply migration
./scripts/migrations/migrate.sh --apply 007

# 5. Verify and test
curl http://staging.yourdomain.com/health
# Test all features
```

### Production

```bash
# 1. Schedule maintenance window (if needed)
# 2. Notify users

# 3. Backup database
./scripts/backup/backup.sh --docker --compress

# 4. Stop traffic (optional for quick migrations)
# nginx: maintenance mode

# 5. Apply migration
./scripts/migrations/migrate.sh --apply 007

# 6. Verify integrity
sqlite3 data/app.db "PRAGMA integrity_check;"

# 7. Restart application
docker-compose -f docker-compose.production.yml restart mcp

# 8. Verify health
curl https://yourdomain.com/health/ready

# 9. Enable traffic
# nginx: disable maintenance mode

# 10. Monitor logs
docker-compose logs -f mcp
```

---

## Rollback Procedures

### Option 1: Restore from Backup (Recommended)

```bash
# 1. Stop server
docker-compose stop mcp

# 2. Restore pre-migration backup
./scripts/backup/restore.sh backups/pre-migration-v007-DATE.db

# 3. Start server
docker-compose start mcp

# 4. Verify
curl http://localhost:8080/health
```

### Option 2: Execute Rollback SQL

```bash
# 1. Get rollback SQL
sqlite3 data/app.db "
SELECT rollback_sql FROM schema_version WHERE version = 7;
"

# 2. Execute rollback SQL
# (Copy the SQL and execute carefully)

# 3. Remove version record
sqlite3 data/app.db "
DELETE FROM schema_version WHERE version = 7;
"

# 4. Verify
./scripts/migrations/migrate.sh
```

---

## Zero-Downtime Migrations

For production deployments that require zero downtime:

### Strategy 1: Backward Compatible Changes

**Add Column (Safe):**
```sql
-- Adding optional column is safe
ALTER TABLE table_name ADD COLUMN new_column TEXT;

-- Deploy new code
-- Old code ignores new column
-- New code uses new column
```

### Strategy 2: Multi-Step Migration

**Step 1: Add Column**
```sql
ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 0;
```

**Deploy:** New code checks email_verified (defaults to 0)

**Step 2: Backfill Data**
```sql
UPDATE users SET email_verified = 1 WHERE email IS NOT NULL;
```

**Step 3: Make Required (Later)**
```sql
-- After all users migrated, can add NOT NULL constraint
```

### Strategy 3: Blue-Green Deployment

1. Deploy new version to "green" environment
2. Run migrations on green database
3. Switch traffic to green
4. Keep blue as fallback

---

## Schema Version History

### Current Schema (Version 2)

**Version 001:** Initial schema
- Tables: tenants, stores, audit_log, sessions, magic_links, webhook_events, master_key_metadata
- Indexes: All primary keys and foreign key indexes

**Version 002:** Store config caching
- Added: `stores.store_config` (TEXT)
- Added: `stores.config_fetched_at` (TIMESTAMP)
- Index: `idx_stores_config_fetched`

**Future versions:** Track here as migrations are applied

---

## Migration Testing

### Test Checklist

**Before Applying:**
- [ ] Backup created and verified
- [ ] SQL syntax validated
- [ ] Migration tested on copy of database
- [ ] Rollback SQL tested
- [ ] Performance impact estimated

**During Application:**
- [ ] Monitor logs for errors
- [ ] Check for lock timeouts
- [ ] Verify version updated

**After Application:**
- [ ] Database integrity check passed
- [ ] All tables accessible
- [ ] Application starts successfully
- [ ] Health checks passing
- [ ] Critical features tested
- [ ] Performance acceptable

---

## Troubleshooting

### "table schema_version already exists"

This is normal - the table is created automatically on first migration.

### "cannot add a column with non-constant default"

SQLite limitation. Use a two-step process:
```sql
-- Step 1: Add nullable column
ALTER TABLE table_name ADD COLUMN new_column TEXT;

-- Step 2: Update with default
UPDATE table_name SET new_column = 'default' WHERE new_column IS NULL;
```

### "database disk image is malformed"

Database corruption. Restore from backup immediately:
```bash
./scripts/backup/restore.sh --docker backups/LATEST.db.gz
```

### "attempt to write a readonly database"

Permission issue. Fix with:
```bash
# Fix permissions
chmod 644 data/app.db

# Or in Docker
docker-compose exec mcp chmod 644 /app/data/app.db
```

---

## Links

- [BACKUP_RECOVERY.md](BACKUP_RECOVERY.md) - Backup procedures
- [PRODUCTION-RUNBOOK.md](PRODUCTION-RUNBOOK.md) - Operations guide  
- [../scripts/migrations/README.md](../scripts/migrations/README.md) - Migration script docs

