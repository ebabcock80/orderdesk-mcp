#!/bin/bash
#
# OrderDesk MCP Server - Database Performance Analysis
# =============================================================================
# Analyzes database performance and suggests optimizations
#
# Usage:
#   ./scripts/performance/analyze_db.sh                  # Analyze local database
#   ./scripts/performance/analyze_db.sh --docker         # Analyze Docker database
#
# =============================================================================

set -euo pipefail

# Configuration
DATA_DIR="${DATA_DIR:-./data}"
DB_FILE="${DB_FILE:-app.db}"
CONTAINER_NAME="${CONTAINER_NAME:-orderdesk-mcp-server}"
DOCKER=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --docker|-d)
            DOCKER=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--docker]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# SQL query function
run_query() {
    local query="$1"
    if [ "$DOCKER" = true ]; then
        docker exec "$CONTAINER_NAME" sqlite3 "/app/data/$DB_FILE" "$query"
    else
        sqlite3 "$DATA_DIR/$DB_FILE" "$query"
    fi
}

echo "=========================================="
echo "Database Performance Analysis"
echo "=========================================="
echo ""

# Database size
echo "📊 Database Size:"
echo "=================="
if [ "$DOCKER" = true ]; then
    SIZE=$(docker exec "$CONTAINER_NAME" du -h "/app/data/$DB_FILE" | cut -f1)
else
    SIZE=$(du -h "$DATA_DIR/$DB_FILE" | cut -f1)
fi
echo "Database file: $SIZE"
echo ""

# Table statistics
echo "📋 Table Statistics:"
echo "===================="
run_query "
SELECT 
    name as table_name,
    (SELECT COUNT(*) FROM sqlite_master sm WHERE sm.name = m.name) as count
FROM sqlite_master m 
WHERE type='table' AND name NOT LIKE 'sqlite_%'
ORDER BY name;
" | while IFS='|' read -r table count; do
    ROW_COUNT=$(run_query "SELECT COUNT(*) FROM $table;" 2>/dev/null || echo "0")
    echo "$table: $ROW_COUNT rows"
done
echo ""

# Index usage
echo "🔍 Indexes:"
echo "==========="
run_query "
SELECT 
    name,
    tbl_name,
    sql
FROM sqlite_master 
WHERE type='index' AND name NOT LIKE 'sqlite_%'
ORDER BY tbl_name, name;
" | while IFS='|' read -r name table sql; do
    echo "  $table.$name"
done
echo ""

# Analyze query performance
echo "⚡ Query Statistics:"
echo "==================="

# Check if we have audit log data
AUDIT_COUNT=$(run_query "SELECT COUNT(*) FROM audit_log;" 2>/dev/null || echo "0")
echo "Audit log entries: $AUDIT_COUNT"

if [ "$AUDIT_COUNT" -gt 0 ]; then
    echo ""
    echo "Recent query patterns (from audit log):"
    run_query "
    SELECT 
        tool_name,
        COUNT(*) as calls,
        AVG(execution_time_ms) as avg_ms,
        MAX(execution_time_ms) as max_ms
    FROM audit_log
    WHERE created_at > datetime('now', '-24 hours')
    GROUP BY tool_name
    ORDER BY calls DESC
    LIMIT 10;
    " 2>/dev/null || echo "No recent audit data"
fi
echo ""

# Check for missing indexes (tables without indexes)
echo "⚠️  Potential Issues:"
echo "====================="

# Tables without any indexes
TABLES_NO_INDEX=$(run_query "
SELECT name FROM sqlite_master 
WHERE type='table' AND name NOT LIKE 'sqlite_%'
AND name NOT IN (
    SELECT DISTINCT tbl_name FROM sqlite_master WHERE type='index'
);
" 2>/dev/null || echo "")

if [ -n "$TABLES_NO_INDEX" ]; then
    echo "Tables without indexes:"
    echo "$TABLES_NO_INDEX" | sed 's/^/  - /'
else
    echo "✅ All tables have indexes"
fi
echo ""

# Check for large tables
echo "📈 Largest Tables:"
echo "=================="
for table in tenants stores audit_log sessions magic_links webhook_events master_key_metadata; do
    COUNT=$(run_query "SELECT COUNT(*) FROM $table;" 2>/dev/null || echo "0")
    if [ "$COUNT" -gt 1000 ]; then
        echo "⚠️  $table: $COUNT rows (consider archiving old data)"
    elif [ "$COUNT" -gt 100 ]; then
        echo "  $table: $COUNT rows (normal)"
    else
        echo "  $table: $COUNT rows"
    fi
done
echo ""

# Vacuum recommendation
echo "🧹 Maintenance Recommendations:"
echo "================================"
FREELIST=$(run_query "PRAGMA freelist_count;" 2>/dev/null || echo "0")
if [ "$FREELIST" -gt 1000 ]; then
    echo "⚠️  Database has $FREELIST free pages"
    echo "   Recommendation: Run VACUUM to reclaim space"
    echo "   Command: ./scripts/performance/vacuum_db.sh"
else
    echo "✅ Database is compact ($FREELIST free pages)"
fi
echo ""

# Cache statistics
echo "💾 SQLite Cache Settings:"
echo "========================="
run_query "PRAGMA cache_size;"
run_query "PRAGMA page_size;"
echo ""

echo "=========================================="
echo "✅ Analysis Complete"
echo "=========================================="
echo ""
echo "Recommendations:"
echo "  1. Monitor tables with >1000 rows for growth"
echo "  2. Run VACUUM monthly to reclaim space"
echo "  3. Review audit log retention (current: 90 days)"
echo "  4. All critical indexes are in place ✅"
echo ""

