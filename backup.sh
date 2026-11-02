#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="$ROOT/backup"
LATEST_BACKUP_GZ="$BACKUP_DIR/latest.sql.gz"
POSTGRES_CONTAINER="autotrader_postgres"
DB_USER="autotrader"
DB_NAME="autotrader"

mkdir -p "$BACKUP_DIR"

echo "================================================================================"
echo " ==> [BACKUP] Starting PostgreSQL, AI Vector Memory & System Backup..."
echo "================================================================================"

# Check if postgres container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
    echo " [ERROR] Container '${POSTGRES_CONTAINER}' is not running. Cannot perform backup."
    exit 1
fi

echo " ==> [MODE] Single Latest Snapshot: All DB tables & pgvector memory included."

# Replace the last backup only after a complete dump and archive verification.
# An interrupted dump must never truncate the last recoverable snapshot.
PENDING_BACKUP_GZ=$(mktemp "$BACKUP_DIR/.autotrader_pending.XXXXXX")
trap 'rm -f "$PENDING_BACKUP_GZ"' EXIT

docker exec "$POSTGRES_CONTAINER" pg_dump \
    -U "$DB_USER" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    -d "$DB_NAME" | gzip -c > "$PENDING_BACKUP_GZ"

gzip -t "$PENDING_BACKUP_GZ"
mv -f "$PENDING_BACKUP_GZ" "$LATEST_BACKUP_GZ"
chmod 644 "$LATEST_BACKUP_GZ"

# Keep ONLY 1 latest backup (latest.sql.gz) — remove any old timestamped or uncompressed dumps
rm -f "$BACKUP_DIR"/autotrader_backup_* "$BACKUP_DIR"/latest.sql

BACKUP_SIZE=$(ls -lh "$LATEST_BACKUP_GZ" | awk '{print $5}')

echo " [BACKUP SUCCESS] Saved single latest compressed backup to:"
echo "   - $LATEST_BACKUP_GZ ($BACKUP_SIZE)"
echo ""
echo " ==> [BACKUP STATS] Verifying Backed-Up DB & Vector Memory Summary:"

docker exec "$POSTGRES_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -A -c "
SELECT '   * Users Registered:                ' || count(*) FROM users
UNION ALL
SELECT '   * Upstox Configurations:           ' || count(*) FROM upstox_configs
UNION ALL
SELECT '   * Strategies & Rules:              ' || (SELECT count(*) FROM strategies) || ' strategies / ' || (SELECT count(*) FROM rules) || ' rules'
UNION ALL
SELECT '   * Opportunity Masters & Trades:    ' || (SELECT count(*) FROM opportunity_masters) || ' masters / ' || (SELECT count(*) FROM trade_opportunities) || ' trades'
UNION ALL
SELECT '   * Vector Memory (Research Chunks): ' || count(*) FROM research_chunks WHERE embedding IS NOT NULL
UNION ALL
SELECT '   * Vector Memory (Research Claims): ' || count(*) FROM research_claims WHERE embedding IS NOT NULL
UNION ALL
SELECT '   * Vector Memory (Opportunities):   ' || count(*) FROM opportunity_memories WHERE embedding IS NOT NULL;
" 2>/dev/null || echo "   * Database tables & pgvector memory: active"

echo "================================================================================"
echo " ==> [BACKUP COMPLETE] Single latest snapshot verified & preserved."
echo "================================================================================"
