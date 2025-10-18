#!/bin/bash
#
# OrderDesk MCP Server - Database Restore Script
# =============================================================================
# Restores a database backup with verification and optional dry-run
#
# Usage:
#   ./scripts/backup/restore.sh backup-file.db           # Local restore
#   ./scripts/backup/restore.sh --docker backup-file.db  # Docker restore
#   ./scripts/backup/restore.sh --dry-run backup-file.db # Preview only
#
# =============================================================================

set -euo pipefail

# Configuration
DATA_DIR="${DATA_DIR:-./data}"
DB_FILE="${DB_FILE:-app.db}"
CONTAINER_NAME="${CONTAINER_NAME:-orderdesk-mcp-server}"

# Parse arguments
DOCKER=false
DRY_RUN=false
BACKUP_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --docker|-d)
            DOCKER=true
            shift
            ;;
        --dry-run|--preview|-p)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--docker] [--dry-run] <backup-file>"
            echo ""
            echo "Arguments:"
            echo "  backup-file     Path to backup file (.db or .db.gz)"
            echo ""
            echo "Options:"
            echo "  --docker, -d       Restore to Docker container"
            echo "  --dry-run, -p      Preview restore without making changes"
            echo "  --help, -h         Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  DATA_DIR        Data directory (default: ./data)"
            echo "  DB_FILE         Database filename (default: app.db)"
            echo "  CONTAINER_NAME  Docker container name (default: orderdesk-mcp-server)"
            echo ""
            echo "Examples:"
            echo "  $0 backups/orderdesk-mcp-20251018_120000.db"
            echo "  $0 --docker backups/orderdesk-mcp-20251018_120000.db.gz"
            echo "  $0 --dry-run backups/orderdesk-mcp-20251018_120000.db"
            exit 0
            ;;
        *)
            if [ -z "$BACKUP_FILE" ]; then
                BACKUP_FILE="$1"
            else
                echo "ERROR: Unknown argument: $1"
                exit 1
            fi
            shift
            ;;
    esac
done

# Validate backup file argument
if [ -z "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not specified"
    echo "Usage: $0 [--docker] [--dry-run] <backup-file>"
    exit 1
fi

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    echo ""
    echo "Available backups:"
    ls -lh backups/ 2>/dev/null || echo "  No backups found"
    exit 1
fi

echo "=========================================="
echo "OrderDesk MCP Server - Database Restore"
echo "=========================================="
echo "Backup file: $BACKUP_FILE"
echo "Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"
echo "Docker mode: $DOCKER"
echo "Dry run: $DRY_RUN"
echo ""

# Handle compressed backups
TEMP_UNCOMPRESSED=""
if [[ "$BACKUP_FILE" == *.gz ]]; then
    echo "Decompressing backup..."
    TEMP_UNCOMPRESSED="/tmp/orderdesk-restore-$$.db"
    gunzip -c "$BACKUP_FILE" > "$TEMP_UNCOMPRESSED" || {
        echo "ERROR: Failed to decompress backup"
        exit 1
    }
    BACKUP_FILE="$TEMP_UNCOMPRESSED"
    echo "✅ Decompressed to: $BACKUP_FILE"
fi

# Verify backup integrity
echo "Verifying backup integrity..."
sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" | grep -q "ok" || {
    echo "ERROR: Backup file is corrupt!"
    [ -n "$TEMP_UNCOMPRESSED" ] && rm -f "$TEMP_UNCOMPRESSED"
    exit 1
}
echo "✅ Backup integrity verified"

# Show backup info
echo ""
echo "Backup Information:"
echo "-------------------"
TABLES=$(sqlite3 "$BACKUP_FILE" "SELECT count(*) FROM sqlite_master WHERE type='table';")
TENANTS=$(sqlite3 "$BACKUP_FILE" "SELECT count(*) FROM tenants;" 2>/dev/null || echo "N/A")
STORES=$(sqlite3 "$BACKUP_FILE" "SELECT count(*) FROM stores;" 2>/dev/null || echo "N/A")
echo "Tables: $TABLES"
echo "Tenants: $TENANTS"
echo "Stores: $STORES"
echo ""

# Dry run - exit here
if [ "$DRY_RUN" = true ]; then
    echo "=========================================="
    echo "✅ Dry Run Complete (No Changes Made)"
    echo "=========================================="
    echo "Backup file is valid and can be restored."
    echo ""
    echo "To perform actual restore, run:"
    if [ "$DOCKER" = true ]; then
        echo "  $0 --docker $(basename "$BACKUP_FILE")"
    else
        echo "  $0 $(basename "$BACKUP_FILE")"
    fi
    [ -n "$TEMP_UNCOMPRESSED" ] && rm -f "$TEMP_UNCOMPRESSED"
    exit 0
fi

# Confirm restore (destructive operation!)
echo "⚠️  WARNING: This will REPLACE the current database!"
echo ""
if [ "$DOCKER" = true ]; then
    echo "Target: Docker container '$CONTAINER_NAME'"
else
    echo "Target: $DATA_DIR/$DB_FILE"
fi
echo ""
read -p "Are you sure you want to continue? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Restore cancelled by user"
    [ -n "$TEMP_UNCOMPRESSED" ] && rm -f "$TEMP_UNCOMPRESSED"
    exit 0
fi

# Create backup of current database before restore
CURRENT_BACKUP="$BACKUP_DIR/pre-restore-$(date +%Y%m%d_%H%M%S).db"

if [ "$DOCKER" = true ]; then
    echo "Creating backup of current database..."
    docker exec "$CONTAINER_NAME" sqlite3 "/app/data/$DB_FILE" ".backup '/app/data/pre-restore.db'" || true
    docker cp "$CONTAINER_NAME:/app/data/pre-restore.db" "$CURRENT_BACKUP" || true
    docker exec "$CONTAINER_NAME" rm "/app/data/pre-restore.db" || true
    echo "✅ Current database backed up to: $CURRENT_BACKUP"
else
    if [ -f "$DATA_DIR/$DB_FILE" ]; then
        echo "Creating backup of current database..."
        cp "$DATA_DIR/$DB_FILE" "$CURRENT_BACKUP"
        echo "✅ Current database backed up to: $CURRENT_BACKUP"
    fi
fi

# Perform restore
echo ""
echo "Restoring database..."

if [ "$DOCKER" = true ]; then
    # Stop the container
    echo "Stopping container..."
    docker-compose stop mcp || docker stop "$CONTAINER_NAME" || true
    
    # Copy backup into container
    docker cp "$BACKUP_FILE" "$CONTAINER_NAME:/app/data/$DB_FILE" || {
        echo "ERROR: Failed to copy backup to container"
        echo "Attempting to restore original database..."
        docker cp "$CURRENT_BACKUP" "$CONTAINER_NAME:/app/data/$DB_FILE" || true
        exit 1
    }
    
    # Start the container
    echo "Starting container..."
    docker-compose start mcp || docker start "$CONTAINER_NAME" || true
    
else
    # Direct file copy
    cp "$BACKUP_FILE" "$DATA_DIR/$DB_FILE" || {
        echo "ERROR: Failed to restore database"
        echo "Attempting to restore original database..."
        cp "$CURRENT_BACKUP" "$DATA_DIR/$DB_FILE" || true
        exit 1
    }
fi

echo "✅ Database restored successfully"

# Cleanup
[ -n "$TEMP_UNCOMPRESSED" ] && rm -f "$TEMP_UNCOMPRESSED"

# Verify restored database
echo ""
echo "Verifying restored database..."
if [ "$DOCKER" = true ]; then
    RESTORED_TABLES=$(docker exec "$CONTAINER_NAME" sqlite3 "/app/data/$DB_FILE" "SELECT count(*) FROM sqlite_master WHERE type='table';")
    RESTORED_TENANTS=$(docker exec "$CONTAINER_NAME" sqlite3 "/app/data/$DB_FILE" "SELECT count(*) FROM tenants;" 2>/dev/null || echo "N/A")
else
    RESTORED_TABLES=$(sqlite3 "$DATA_DIR/$DB_FILE" "SELECT count(*) FROM sqlite_master WHERE type='table';")
    RESTORED_TENANTS=$(sqlite3 "$DATA_DIR/$DB_FILE" "SELECT count(*) FROM tenants;" 2>/dev/null || echo "N/A")
fi

echo "Restored tables: $RESTORED_TABLES"
echo "Restored tenants: $RESTORED_TENANTS"

echo ""
echo "=========================================="
echo "✅ Restore Complete!"
echo "=========================================="
echo "Backup file: $BACKUP_FILE"
echo "Pre-restore backup: $CURRENT_BACKUP"
echo ""
echo "If something went wrong, you can restore the previous state:"
if [ "$DOCKER" = true ]; then
    echo "  ./scripts/backup/restore.sh --docker $CURRENT_BACKUP"
else
    echo "  ./scripts/backup/restore.sh $CURRENT_BACKUP"
fi
echo ""

