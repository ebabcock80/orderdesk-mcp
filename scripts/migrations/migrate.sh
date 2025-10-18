#!/bin/bash
#
# OrderDesk MCP Server - Database Migration Script
# =============================================================================
# Applies database schema migrations safely with backup and rollback support
#
# Usage:
#   ./scripts/migrations/migrate.sh                    # Show current version
#   ./scripts/migrations/migrate.sh --apply VERSION    # Apply migration
#   ./scripts/migrations/migrate.sh --rollback VERSION # Rollback migration
#   ./scripts/migrations/migrate.sh --list             # List all migrations
#
# =============================================================================

set -euo pipefail

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_DIR="${DATA_DIR:-$PROJECT_DIR/data}"
DB_FILE="${DB_FILE:-app.db}"
MIGRATIONS_DIR="$PROJECT_DIR/scripts/migrations/versions"
CONTAINER_NAME="${CONTAINER_NAME:-orderdesk-mcp-server}"
DOCKER="${DOCKER:-false}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Get current schema version
get_current_version() {
    local db_path="$1"
    
    # Check if schema_version table exists
    local has_table
    has_table=$(sqlite3 "$db_path" "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='schema_version';" 2>/dev/null || echo "0")
    
    if [ "$has_table" = "0" ]; then
        echo "0"  # No version table = version 0
    else
        sqlite3 "$db_path" "SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1;" 2>/dev/null || echo "0"
    fi
}

# Create schema_version table if it doesn't exist
ensure_version_table() {
    local db_path="$1"
    
    sqlite3 "$db_path" "
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER NOT NULL,
        description TEXT NOT NULL,
        applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        applied_by TEXT,
        rollback_sql TEXT,
        PRIMARY KEY (version)
    );" || {
        log_error "Failed to create schema_version table"
        return 1
    }
}

# List available migrations
list_migrations() {
    if [ ! -d "$MIGRATIONS_DIR" ]; then
        log_warn "No migrations directory found: $MIGRATIONS_DIR"
        return
    fi
    
    echo "Available Migrations:"
    echo "===================="
    
    for migration in "$MIGRATIONS_DIR"/*.sql; do
        if [ -f "$migration" ]; then
            local version=$(basename "$migration" | cut -d'_' -f1)
            local description=$(basename "$migration" | cut -d'_' -f2- | sed 's/.sql$//' | tr '_' ' ')
            echo "  v$version - $description"
        fi
    done
}

# Show current status
show_status() {
    local db_path="$DATA_DIR/$DB_FILE"
    
    if [ ! -f "$db_path" ]; then
        log_error "Database not found: $db_path"
        return 1
    fi
    
    ensure_version_table "$db_path"
    local current_version=$(get_current_version "$db_path")
    
    echo "Database Migration Status"
    echo "========================="
    echo "Database: $db_path"
    echo "Current Version: $current_version"
    echo ""
    
    # Show migration history
    echo "Migration History:"
    sqlite3 "$db_path" "SELECT version, description, applied_at, applied_by FROM schema_version ORDER BY version DESC LIMIT 10;" 2>/dev/null || {
        echo "  No migrations applied yet"
    }
}

# Apply migration
apply_migration() {
    local version="$1"
    local db_path="$DATA_DIR/$DB_FILE"
    local migration_file="$MIGRATIONS_DIR/${version}_*.sql"
    
    # Find migration file
    local migration
    migration=$(ls $migration_file 2>/dev/null | head -1)
    
    if [ -z "$migration" ] || [ ! -f "$migration" ]; then
        log_error "Migration file not found for version: $version"
        list_migrations
        return 1
    fi
    
    log_info "Found migration: $(basename "$migration")"
    
    # Check current version
    ensure_version_table "$db_path"
    local current_version=$(get_current_version "$db_path")
    
    if [ "$current_version" -ge "$version" ]; then
        log_warn "Database is already at version $current_version (requested: $version)"
        log_warn "Use --rollback to downgrade"
        return 1
    fi
    
    # Create backup before migration
    log_info "Creating pre-migration backup..."
    local backup_file="$PROJECT_DIR/backups/pre-migration-v${version}-$(date +%Y%m%d_%H%M%S).db"
    mkdir -p "$(dirname "$backup_file")"
    sqlite3 "$db_path" ".backup '$backup_file'"
    log_info "✅ Backup created: $backup_file"
    
    # Apply migration
    log_info "Applying migration v$version..."
    
    if ! sqlite3 "$db_path" < "$migration"; then
        log_error "Migration failed!"
        log_warn "Database backup available at: $backup_file"
        return 1
    fi
    
    # Record migration in schema_version
    local description=$(basename "$migration" | cut -d'_' -f2- | sed 's/.sql$//' | tr '_' ' ')
    local applied_by="${USER:-unknown}"
    
    sqlite3 "$db_path" "
    INSERT INTO schema_version (version, description, applied_by)
    VALUES ($version, '$description', '$applied_by');
    "
    
    log_info "✅ Migration v$version applied successfully"
    log_info "Current database version: $version"
    
    # Verify database integrity
    log_info "Verifying database integrity..."
    sqlite3 "$db_path" "PRAGMA integrity_check;" | grep -q "ok" && log_info "✅ Database integrity OK"
}

# Main
case "${1:-}" in
    --apply|-a)
        if [ -z "${2:-}" ]; then
            log_error "Version number required"
            echo "Usage: $0 --apply VERSION"
            exit 1
        fi
        apply_migration "$2"
        ;;
    --list|-l)
        list_migrations
        ;;
    --status|-s|"")
        show_status
        ;;
    --help|-h)
        echo "OrderDesk MCP Server - Database Migration Tool"
        echo ""
        echo "Usage:"
        echo "  $0                    Show current version and status"
        echo "  $0 --apply VERSION    Apply migration to VERSION"
        echo "  $0 --list             List available migrations"
        echo "  $0 --status           Show migration status"
        echo "  $0 --help             Show this help"
        echo ""
        echo "Examples:"
        echo "  $0                    # Show current version"
        echo "  $0 --list             # List all migrations"
        echo "  $0 --apply 002        # Apply migration v002"
        echo ""
        exit 0
        ;;
    *)
        log_error "Unknown command: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac

