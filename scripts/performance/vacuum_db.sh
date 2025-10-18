#!/bin/bash
#
# OrderDesk MCP Server - Database Vacuum and Optimization
# =============================================================================
# Reclaims unused space and optimizes database performance
#
# Usage:
#   ./scripts/performance/vacuum_db.sh                  # Vacuum local database
#   ./scripts/performance/vacuum_db.sh --docker         # Vacuum Docker database
#   ./scripts/performance/vacuum_db.sh --analyze        # VACUUM + ANALYZE
#
# =============================================================================

set -euo pipefail

# Configuration
DATA_DIR="${DATA_DIR:-./data}"
DB_FILE="${DB_FILE:-app.db}"
CONTAINER_NAME="${CONTAINER_NAME:-orderdesk-mcp-server}"
DOCKER=false
ANALYZE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --docker|-d)
            DOCKER=true
            shift
            ;;
        --analyze|-a)
            ANALYZE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--docker] [--analyze]"
            echo ""
            echo "Options:"
            echo "  --docker, -d   Vacuum Docker database"
            echo "  --analyze, -a  Run ANALYZE after VACUUM (recommended)"
            echo ""
            echo "VACUUM reclaims unused space and defragments the database"
            echo "ANALYZE updates query optimizer statistics"
            echo ""
            echo "Run monthly or after large deletions"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "Database Vacuum and Optimization"
echo "=========================================="
echo ""

# Get database size before
echo "Checking database size..."
if [ "$DOCKER" = true ]; then
    SIZE_BEFORE=$(docker exec "$CONTAINER_NAME" stat -c %s "/app/data/$DB_FILE" 2>/dev/null || echo "0")
else
    SIZE_BEFORE=$(stat -f %z "$DATA_DIR/$DB_FILE" 2>/dev/null || stat -c %s "$DATA_DIR/$DB_FILE" 2>/dev/null || echo "0")
fi
SIZE_BEFORE_MB=$(echo "scale=2; $SIZE_BEFORE / 1024 / 1024" | bc)
echo "Size before: ${SIZE_BEFORE_MB}MB"
echo ""

# Create backup before vacuum
echo "Creating backup before vacuum..."
./scripts/backup/backup.sh $([ "$DOCKER" = true ] && echo "--docker") --compress || {
    echo "ERROR: Failed to create backup"
    exit 1
}
echo ""

# Stop application (vacuum requires exclusive access)
if [ "$DOCKER" = true ]; then
    echo "Stopping application..."
    docker-compose stop mcp
    echo ""
fi

# Run VACUUM
echo "Running VACUUM..."
START_TIME=$(date +%s)

if [ "$DOCKER" = true ]; then
    docker exec "$CONTAINER_NAME" sqlite3 "/app/data/$DB_FILE" "VACUUM;" || {
        echo "ERROR: VACUUM failed"
        docker-compose start mcp
        exit 1
    }
else
    sqlite3 "$DATA_DIR/$DB_FILE" "VACUUM;" || {
        echo "ERROR: VACUUM failed"
        exit 1
    }
fi

VACUUM_TIME=$(($(date +%s) - START_TIME))
echo "✅ VACUUM completed in ${VACUUM_TIME}s"
echo ""

# Run ANALYZE if requested
if [ "$ANALYZE" = true ]; then
    echo "Running ANALYZE..."
    START_TIME=$(date +%s)
    
    if [ "$DOCKER" = true ]; then
        docker exec "$CONTAINER_NAME" sqlite3 "/app/data/$DB_FILE" "ANALYZE;" || {
            echo "ERROR: ANALYZE failed"
        }
    else
        sqlite3 "$DATA_DIR/$DB_FILE" "ANALYZE;" || {
            echo "ERROR: ANALYZE failed"
        }
    fi
    
    ANALYZE_TIME=$(($(date +%s) - START_TIME))
    echo "✅ ANALYZE completed in ${ANALYZE_TIME}s"
    echo ""
fi

# Start application
if [ "$DOCKER" = true ]; then
    echo "Starting application..."
    docker-compose start mcp
    sleep 3
    echo ""
fi

# Get database size after
echo "Checking database size..."
if [ "$DOCKER" = true ]; then
    SIZE_AFTER=$(docker exec "$CONTAINER_NAME" stat -c %s "/app/data/$DB_FILE" 2>/dev/null || echo "0")
else
    SIZE_AFTER=$(stat -f %z "$DATA_DIR/$DB_FILE" 2>/dev/null || stat -c %s "$DATA_DIR/$DB_FILE" 2>/dev/null || echo "0")
fi
SIZE_AFTER_MB=$(echo "scale=2; $SIZE_AFTER / 1024 / 1024" | bc)
SAVED=$(echo "scale=2; ($SIZE_BEFORE - $SIZE_AFTER) / 1024 / 1024" | bc)
PERCENT=$(echo "scale=1; ($SIZE_BEFORE - $SIZE_AFTER) * 100 / $SIZE_BEFORE" | bc 2>/dev/null || echo "0")

echo "Size after:  ${SIZE_AFTER_MB}MB"
echo "Space saved: ${SAVED}MB (${PERCENT}%)"
echo ""

# Verify database integrity
echo "Verifying database integrity..."
if [ "$DOCKER" = true ]; then
    INTEGRITY=$(docker exec "$CONTAINER_NAME" sqlite3 "/app/data/$DB_FILE" "PRAGMA integrity_check;")
else
    INTEGRITY=$(sqlite3 "$DATA_DIR/$DB_FILE" "PRAGMA integrity_check;")
fi

if [ "$INTEGRITY" = "ok" ]; then
    echo "✅ Database integrity OK"
else
    echo "⚠️  Integrity check failed: $INTEGRITY"
fi
echo ""

# Verify application health
if [ "$DOCKER" = true ]; then
    echo "Verifying application health..."
    sleep 2
    if curl -s http://localhost:8080/health | grep -q "ok"; then
        echo "✅ Application healthy"
    else
        echo "⚠️  Health check failed"
    fi
    echo ""
fi

echo "=========================================="
echo "✅ Vacuum Complete!"
echo "=========================================="
echo "Database size: ${SIZE_BEFORE_MB}MB → ${SIZE_AFTER_MB}MB"
echo "Space saved: ${SAVED}MB (${PERCENT}%)"
echo "VACUUM time: ${VACUUM_TIME}s"
[ "$ANALYZE" = true ] && echo "ANALYZE time: ${ANALYZE_TIME}s"
echo ""
echo "Recommendations:"
echo "  - Run VACUUM monthly or after large deletions"
echo "  - Run ANALYZE after significant data changes"
echo "  - Consider archiving old audit logs (>90 days)"
echo ""

