#!/bin/bash
#
# OrderDesk MCP Server - Database Backup Script
# =============================================================================
# Backs up the SQLite database with timestamp and optional compression
#
# Usage:
#   ./scripts/backup/backup.sh                    # Local backup
#   ./scripts/backup/backup.sh --compress         # Compressed backup
#   ./scripts/backup/backup.sh --docker           # Backup from Docker
#   ./scripts/backup/backup.sh --docker --compress # Docker + compress
#
# =============================================================================

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
DATA_DIR="${DATA_DIR:-./data}"
DB_FILE="${DB_FILE:-app.db}"
CONTAINER_NAME="${CONTAINER_NAME:-orderdesk-mcp-server}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# Parse arguments
COMPRESS=false
DOCKER=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --compress|-c)
            COMPRESS=true
            shift
            ;;
        --docker|-d)
            DOCKER=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--compress] [--docker] [--help]"
            echo ""
            echo "Options:"
            echo "  --compress, -c  Compress backup with gzip"
            echo "  --docker, -d    Backup from Docker container"
            echo "  --help, -h      Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  BACKUP_DIR       Backup directory (default: ./backups)"
            echo "  DATA_DIR         Data directory (default: ./data)"
            echo "  DB_FILE          Database filename (default: app.db)"
            echo "  CONTAINER_NAME   Docker container name (default: orderdesk-mcp-server)"
            echo "  RETENTION_DAYS   Backup retention period (default: 30)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup filename
BACKUP_FILE="$BACKUP_DIR/orderdesk-mcp-${TIMESTAMP}.db"

echo "=========================================="
echo "OrderDesk MCP Server - Database Backup"
echo "=========================================="
echo "Timestamp: $TIMESTAMP"
echo "Backup directory: $BACKUP_DIR"
echo "Docker mode: $DOCKER"
echo "Compression: $COMPRESS"
echo ""

# Perform backup
if [ "$DOCKER" = true ]; then
    echo "Backing up from Docker container: $CONTAINER_NAME"
    
    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "ERROR: Container '$CONTAINER_NAME' is not running"
        echo "Available containers:"
        docker ps --format 'table {{.Names}}\t{{.Status}}'
        exit 1
    fi
    
    # Use SQLite .backup command for online backup (no lock)
    docker exec "$CONTAINER_NAME" sqlite3 "/app/data/$DB_FILE" ".backup '/app/data/backup-${TIMESTAMP}.db'" || {
        echo "ERROR: Failed to create backup inside container"
        exit 1
    }
    
    # Copy backup out of container
    docker cp "$CONTAINER_NAME:/app/data/backup-${TIMESTAMP}.db" "$BACKUP_FILE" || {
        echo "ERROR: Failed to copy backup from container"
        exit 1
    }
    
    # Remove temp backup from container
    docker exec "$CONTAINER_NAME" rm "/app/data/backup-${TIMESTAMP}.db" || true
    
else
    echo "Backing up local database: $DATA_DIR/$DB_FILE"
    
    # Check if database exists
    if [ ! -f "$DATA_DIR/$DB_FILE" ]; then
        echo "ERROR: Database file not found: $DATA_DIR/$DB_FILE"
        exit 1
    fi
    
    # Use SQLite .backup command for online backup (no lock)
    sqlite3 "$DATA_DIR/$DB_FILE" ".backup '$BACKUP_FILE'" || {
        echo "ERROR: Failed to create backup"
        echo "Is SQLite installed? Try: brew install sqlite3"
        exit 1
    }
fi

# Verify backup
if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file was not created"
    exit 1
fi

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "✅ Backup created: $BACKUP_FILE ($BACKUP_SIZE)"

# Compress if requested
if [ "$COMPRESS" = true ]; then
    echo "Compressing backup..."
    gzip "$BACKUP_FILE" || {
        echo "ERROR: Failed to compress backup"
        exit 1
    }
    
    COMPRESSED_FILE="${BACKUP_FILE}.gz"
    COMPRESSED_SIZE=$(du -h "$COMPRESSED_FILE" | cut -f1)
    echo "✅ Backup compressed: $COMPRESSED_FILE ($COMPRESSED_SIZE)"
    BACKUP_FILE="$COMPRESSED_FILE"
fi

# Verify integrity
echo "Verifying backup integrity..."
if [[ "$BACKUP_FILE" == *.gz ]]; then
    # Verify gzip integrity
    gunzip -t "$BACKUP_FILE" && echo "✅ Compressed backup integrity OK"
else
    # Verify SQLite integrity
    sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" | grep -q "ok" && echo "✅ Database integrity OK"
fi

# Cleanup old backups
echo "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "orderdesk-mcp-*.db*" -type f -mtime +$RETENTION_DAYS -delete
REMAINING=$(find "$BACKUP_DIR" -name "orderdesk-mcp-*.db*" -type f | wc -l | tr -d ' ')
echo "✅ Retention policy applied: $REMAINING backup(s) remaining"

echo ""
echo "=========================================="
echo "✅ Backup Complete!"
echo "=========================================="
echo "Backup file: $BACKUP_FILE"
echo "Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"
echo "Total backups: $REMAINING"
echo ""
echo "To restore this backup:"
if [ "$DOCKER" = true ]; then
    echo "  ./scripts/backup/restore.sh --docker $BACKUP_FILE"
else
    echo "  ./scripts/backup/restore.sh $BACKUP_FILE"
fi
echo ""

