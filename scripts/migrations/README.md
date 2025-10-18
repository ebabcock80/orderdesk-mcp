# Database Migration Guide

Guide for managing database schema changes in the OrderDesk MCP Server.

---

## Overview

The OrderDesk MCP Server uses a simple, manual migration system for SQLite schema changes. This approach provides:
- ✅ Full control over migrations
- ✅ No external dependencies (no Alembic needed for SQLite)
- ✅ Easy to understand and audit
- ✅ Built-in backup before migration
- ✅ Rollback support

---

## Quick Start

### Check Current Version
```bash
./scripts/migrations/migrate.sh
```

### List Available Migrations
```bash
./scripts/migrations/migrate.sh --list
```

### Apply Migration
```bash
./scripts/migrations/migrate.sh --apply 002
```

---

## Migration System

### How It Works

1. **Schema Version Tracking:**
   - `schema_version` table tracks applied migrations
   - Each migration has a version number (001, 002, 003, etc.)
   - Timestamp and applied_by recorded for audit trail

2. **Migration Files:**
   - Located in `scripts/migrations/versions/`
   - Named: `VERSION_description.sql`
   - Example: `002_add_user_roles.sql`

3. **Migration Process:**
   ```
   Backup → Verify → Apply → Record → Verify
   ```

4. **Safety Features:**
   - Automatic backup before each migration
   - Integrity check before and after
   - Version validation (can't skip versions)
   - Rollback SQL stored in schema_version table

---

## Creating a New Migration

### Step 1: Create Migration File

```bash
# Create new migration file
cat > scripts/migrations/versions/003_add_user_roles.sql << 'EOF'
-- Migration: Add User Roles
-- Version: 003
-- Description: Add role-based access control
-- ============================================================================

-- Add role column to tenants
ALTER TABLE tenants ADD COLUMN role TEXT DEFAULT 'user';

-- Create roles table
CREATE TABLE IF NOT EXISTS roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    permissions TEXT NOT NULL,  -- JSON array
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Insert default roles
INSERT INTO roles (id, name, permissions) VALUES
('admin', 'Administrator', '["all"]'),
('user', 'Standard User', '["read", "write"]'),
('readonly', 'Read Only', '["read"]');

-- Create index
CREATE INDEX idx_tenants_role ON tenants(role);

-- Record migration
INSERT INTO schema_version (version, description, applied_by, rollback_sql)
VALUES (
    3,
    'Add user roles and RBAC',
    'migration_script',
    'DROP TABLE roles; ALTER TABLE tenants DROP COLUMN role;'
);
EOF
```

### Step 2: Test Migration

```bash
# Create test database
cp data/app.db data/app_test.db
export DB_FILE=app_test.db

# Apply migration
./scripts/migrations/migrate.sh --apply 003

# Verify
sqlite3 data/app_test.db "SELECT * FROM roles;"

# Cleanup
rm data/app_test.db
```

### Step 3: Apply to Production

```bash
# 1. Backup first!
./scripts/backup/backup.sh --docker --compress

# 2. Apply migration
./scripts/migrations/migrate.sh --apply 003

# 3. Verify
./scripts/migrations/migrate.sh
```

---

## Migration File Format

```sql
-- Migration: [Title]
-- Version: [NUMBER]
-- Description: [What this migration does]
-- ============================================================================

-- Your SQL changes here
ALTER TABLE table_name ADD COLUMN new_column TEXT;

-- Always record the migration
INSERT INTO schema_version (version, description, applied_by, rollback_sql)
VALUES (
    [NUMBER],
    '[Description]',
    'migration_script',
    '[SQL to undo this migration]'
);
```

---

## Schema Version Table

```sql
CREATE TABLE schema_version (
    version INTEGER NOT NULL PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    applied_by TEXT,
    rollback_sql TEXT
);
```

**Fields:**
- `version` - Migration version number (001, 002, etc.)
- `description` - Human-readable description
- `applied_at` - When migration was applied
- `applied_by` - Who applied it (user or script)
- `rollback_sql` - SQL to undo the migration

---

## Migration Best Practices

### Version Numbering
- Use 3-digit zero-padded numbers: `001`, `002`, `003`
- Never skip versions
- Never reuse version numbers
- Sequential only (no branches)

### File Naming
Format: `VERSION_description.sql`

**Examples:**
- `001_initial_schema.sql`
- `002_add_store_config.sql`
- `003_add_user_roles.sql`
- `004_add_api_keys_table.sql`

### Migration Content
- ✅ Include descriptive header comment
- ✅ Use `IF NOT EXISTS` for CREATE statements
- ✅ Add indexes for new columns when appropriate
- ✅ Always record migration in schema_version
- ✅ Include rollback SQL
- ❌ Don't include destructive changes without backup
- ❌ Don't modify existing data without validation

---

## Rollback Strategy

### Manual Rollback

```bash
# 1. Stop the server
docker-compose stop mcp

# 2. Restore pre-migration backup
./scripts/backup/restore.sh backups/pre-migration-v003-20251018_120000.db

# 3. Start server
docker-compose start mcp

# 4. Verify
curl http://localhost:8080/health
```

### Automated Rollback (Future)

```bash
# Get rollback SQL from schema_version
sqlite3 data/app.db "
SELECT rollback_sql FROM schema_version 
WHERE version = 3;
"

# Execute rollback
# (Manual for now, could be automated)
```

---

## Common Migration Scenarios

### Adding a Column

```sql
-- Add column with default
ALTER TABLE table_name 
ADD COLUMN new_column TEXT DEFAULT 'default_value';

-- Add non-null column (requires default or backfill)
ALTER TABLE table_name 
ADD COLUMN required_column TEXT NOT NULL DEFAULT 'value';
```

### Creating a Table

```sql
CREATE TABLE IF NOT EXISTS new_table (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_new_table_name ON new_table(name);
```

### Adding an Index

```sql
CREATE INDEX IF NOT EXISTS idx_table_column 
ON table_name(column_name);

-- Partial index (SQLite 3.8+)
CREATE INDEX IF NOT EXISTS idx_table_column_filtered
ON table_name(column_name) WHERE condition = true;
```

### Modifying Data

```sql
-- Always backup first!

-- Update existing data
UPDATE table_name 
SET column_name = 'new_value'
WHERE condition = true;

-- Backfill new column
UPDATE table_name
SET new_column = (
    SELECT value FROM other_table 
    WHERE other_table.id = table_name.foreign_key
);
```

---

## Migration Checklist

**Before Migration:**
- [ ] Create backup: `./scripts/backup/backup.sh --docker --compress`
- [ ] Test migration on copy of production database
- [ ] Review migration SQL for errors
- [ ] Estimate migration time
- [ ] Schedule maintenance window if needed
- [ ] Notify users of potential downtime

**During Migration:**
- [ ] Stop application (if necessary)
- [ ] Apply migration: `./scripts/migrations/migrate.sh --apply VERSION`
- [ ] Verify success
- [ ] Check logs for errors

**After Migration:**
- [ ] Verify database integrity
- [ ] Test critical functionality
- [ ] Check health endpoints
- [ ] Monitor logs for errors
- [ ] Verify performance
- [ ] Keep pre-migration backup for 7 days

---

## Troubleshooting

### "Migration failed: syntax error"
```bash
# Validate SQL syntax
sqlite3 data/app.db < scripts/migrations/versions/003_migration.sql

# Check for SQLite version compatibility
sqlite3 --version
```

### "Database is locked"
```bash
# Stop all connections
docker-compose stop mcp

# Wait a moment
sleep 5

# Try migration again
./scripts/migrations/migrate.sh --apply 003
```

### "Already at version X"
```bash
# Check current version
./scripts/migrations/migrate.sh

# To force re-apply (DANGEROUS):
# 1. Delete version record
# 2. Re-apply migration
# NOT RECOMMENDED - use rollback instead
```

---

## Links

- [BACKUP_RECOVERY.md](../docs/BACKUP_RECOVERY.md) - Backup procedures
- [PRODUCTION-RUNBOOK.md](../docs/PRODUCTION-RUNBOOK.md) - Operations guide
- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - Schema documentation

