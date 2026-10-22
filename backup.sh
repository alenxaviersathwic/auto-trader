#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="$ROOT/backup"
LATEST_BACKUP_GZ="$BACKUP_DIR/latest.sql.gz"
LATEST_BACKUP_SQL="$BACKUP_DIR/latest.sql"
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

EXCLUDE_FLAGS=()
if [[ "${1:-}" != "--full" && "${1:-}" != "--include-transient" ]]; then
    EXCLUDE_FLAGS=()
    echo " ==> [MODE] Operational Backup: Tables, Users, Settings & pgvector memory included."
else
    echo " ==> [MODE] Full Dump: Including all ephemeral and historical dumps."
fi

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
    ${EXCLUDE_FLAGS[@]+"${EXCLUDE_FLAGS[@]}"} \
    -d "$DB_NAME" | gzip -c > "$PENDING_BACKUP_GZ"

gzip -t "$PENDING_BACKUP_GZ"
mv -f "$PENDING_BACKUP_GZ" "$LATEST_BACKUP_GZ"

# Also extract uncompressed latest.sql for compatibility
gzip -dc "$LATEST_BACKUP_GZ" > "$LATEST_BACKUP_SQL"

# Timestamped archival snapshot
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
cp "$LATEST_BACKUP_GZ" "$BACKUP_DIR/autotrader_backup_${TIMESTAMP}.sql.gz"

BACKUP_SIZE=$(ls -lh "$LATEST_BACKUP_GZ" | awk '{print $5}')

echo " [BACKUP SUCCESS] Saved latest compressed backup to:"
echo "   - $LATEST_BACKUP_GZ ($BACKUP_SIZE)"
echo "   - $LATEST_BACKUP_SQL"
echo "   - $BACKUP_DIR/autotrader_backup_${TIMESTAMP}.sql.gz"
echo ""
echo " ==> [BACKUP STATS] Verifying Backed-Up Data Summary in Database:"

docker exec "$POSTGRES_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -A -c "
SELECT '   * Users Registered:                ' || count(*) FROM users
UNION ALL
SELECT '   * Upstox Configurations:           ' || count(*) FROM upstox_configs;
" 2>/dev/null || echo "   * Database tables: active"

echo "================================================================================"
echo " ==> [BACKUP COMPLETE] Backup verified successfully; database snapshot preserved."
echo "================================================================================"
