#!/bin/bash
#
# OrderDesk MCP Server - Automated Backup Script
# =============================================================================
# Runs automated backups on a schedule with compression and cloud upload
#
# Usage:
#   ./scripts/backup/automated-backup.sh                 # Run backup
#   ./scripts/backup/automated-backup.sh --setup-cron    # Setup cron job
#   ./scripts/backup/automated-backup.sh --test          # Test run
#
# Cron Schedule (recommended):
#   0 2 * * * /path/to/scripts/backup/automated-backup.sh  # Daily at 2 AM
#   0 */6 * * * /path/to/scripts/backup/automated-backup.sh  # Every 6 hours
#
# =============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DOCKER="${DOCKER:-true}"
COMPRESS="${COMPRESS:-true}"

# Cloud upload settings (optional)
ENABLE_CLOUD_UPLOAD="${ENABLE_CLOUD_UPLOAD:-false}"
S3_BUCKET="${S3_BUCKET:-}"
GCS_BUCKET="${GCS_BUCKET:-}"

# Logging
LOG_FILE="${LOG_FILE:-$PROJECT_DIR/logs/backup.log}"
mkdir -p "$(dirname "$LOG_FILE")"

# Parse arguments
case "${1:-}" in
    --setup-cron)
        echo "Setting up automated backup cron job..."
        CRON_CMD="0 2 * * * $SCRIPT_DIR/automated-backup.sh >> $LOG_FILE 2>&1"
        (crontab -l 2>/dev/null | grep -v "$SCRIPT_DIR/automated-backup.sh"; echo "$CRON_CMD") | crontab -
        echo "✅ Cron job installed: Daily backups at 2 AM"
        echo "View with: crontab -l"
        exit 0
        ;;
    --test)
        echo "Running test backup..."
        DOCKER=false
        ;;
    --help|-h)
        echo "Usage: $0 [--setup-cron] [--test] [--help]"
        echo ""
        echo "Options:"
        echo "  --setup-cron  Install cron job for daily backups"
        echo "  --test        Run test backup (local mode)"
        echo "  --help, -h    Show this help message"
        echo ""
        echo "Environment Variables:"
        echo "  BACKUP_DIR            Backup directory (default: ./backups)"
        echo "  RETENTION_DAYS        Days to keep backups (default: 30)"
        echo "  DOCKER                Use Docker mode (default: true)"
        echo "  COMPRESS              Compress backups (default: true)"
        echo "  ENABLE_CLOUD_UPLOAD   Upload to cloud (default: false)"
        echo "  S3_BUCKET             AWS S3 bucket name"
        echo "  GCS_BUCKET            Google Cloud Storage bucket"
        exit 0
        ;;
esac

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=========================================="
log "Starting automated backup"
log "=========================================="

# Run backup script
BACKUP_OPTS=""
[ "$DOCKER" = true ] && BACKUP_OPTS="$BACKUP_OPTS --docker"
[ "$COMPRESS" = true ] && BACKUP_OPTS="$BACKUP_OPTS --compress"

log "Running backup with options: $BACKUP_OPTS"

# Execute backup
if ! "$SCRIPT_DIR/backup.sh" $BACKUP_OPTS 2>&1 | tee -a "$LOG_FILE"; then
    log "ERROR: Backup failed!"
    exit 1
fi

# Get the latest backup file
LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/orderdesk-mcp-*.db* 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    log "ERROR: No backup file created!"
    exit 1
fi

log "✅ Backup created: $LATEST_BACKUP"

# Upload to cloud (if enabled)
if [ "$ENABLE_CLOUD_UPLOAD" = true ]; then
    log "Uploading backup to cloud storage..."
    
    # AWS S3
    if [ -n "$S3_BUCKET" ]; then
        if command -v aws &> /dev/null; then
            log "Uploading to S3: $S3_BUCKET"
            aws s3 cp "$LATEST_BACKUP" "s3://$S3_BUCKET/backups/$(basename "$LATEST_BACKUP")" || {
                log "ERROR: Failed to upload to S3"
            }
            log "✅ Uploaded to S3"
        else
            log "WARNING: aws CLI not found, skipping S3 upload"
        fi
    fi
    
    # Google Cloud Storage
    if [ -n "$GCS_BUCKET" ]; then
        if command -v gsutil &> /dev/null; then
            log "Uploading to GCS: $GCS_BUCKET"
            gsutil cp "$LATEST_BACKUP" "gs://$GCS_BUCKET/backups/$(basename "$LATEST_BACKUP")" || {
                log "ERROR: Failed to upload to GCS"
            }
            log "✅ Uploaded to GCS"
        else
            log "WARNING: gsutil not found, skipping GCS upload"
        fi
    fi
fi

# Cleanup old backups
log "Cleaning up old backups (retention: $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -name "orderdesk-mcp-*.db*" -type f -mtime +$RETENTION_DAYS -delete
REMAINING=$(find "$BACKUP_DIR" -name "orderdesk-mcp-*.db*" -type f | wc -l | tr -d ' ')
log "✅ Retained $REMAINING backup(s)"

# Send notification (optional)
if command -v mail &> /dev/null && [ -n "${NOTIFICATION_EMAIL:-}" ]; then
    echo "Backup completed successfully at $(date)" | mail -s "OrderDesk MCP Backup Success" "$NOTIFICATION_EMAIL"
fi

log "=========================================="
log "✅ Automated backup complete!"
log "=========================================="
log "Latest backup: $LATEST_BACKUP"
log "Total backups: $REMAINING"
log ""

# Cleanup temp files
[ -n "$TEMP_UNCOMPRESSED" ] && rm -f "$TEMP_UNCOMPRESSED"

exit 0

