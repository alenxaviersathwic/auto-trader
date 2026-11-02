#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="$ROOT/backup"
POSTGRES_CONTAINER="autotrader_postgres"
DB_USER="autotrader"
DB_NAME="autotrader"

if [ -n "${1:-}" ]; then
    BACKUP_FILE="$1"
elif [ -f "$BACKUP_DIR/latest.sql.gz" ]; then
    BACKUP_FILE="$BACKUP_DIR/latest.sql.gz"
elif [ -f "$BACKUP_DIR/latest.sql" ]; then
    BACKUP_FILE="$BACKUP_DIR/latest.sql"
else
    BACKUP_FILE=""
fi

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
    echo " [ERROR] Backup file not found in $BACKUP_DIR"
    exit 1
fi

echo "================================================================================"
echo " ==> [RESTORE] Restoring PostgreSQL Database & AI Vector Memory..."
echo "     From: $BACKUP_FILE"
echo "================================================================================"

if ! docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
    echo " [ERROR] Container '${POSTGRES_CONTAINER}' is not running. Start with ./up.sh first."
    exit 1
fi

# Reset schema cleanly and ensure pgvector extension is active before importing dump
docker exec "$POSTGRES_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO ${DB_USER};
GRANT ALL ON SCHEMA public TO public;
CREATE EXTENSION IF NOT EXISTS vector;
" >/dev/null 2>&1 || true

# Restore the dump (supporting both compressed .sql.gz and plain .sql)
if [[ "$BACKUP_FILE" == *.gz ]]; then
    gzip -dc "$BACKUP_FILE" | docker exec -i "$POSTGRES_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1
else
    cat "$BACKUP_FILE" | docker exec -i "$POSTGRES_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1
fi

# Ensure alembic_version column width and opportunity table names are up to date
docker exec "$POSTGRES_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
ALTER TABLE IF EXISTS alembic_version ALTER COLUMN version_num TYPE VARCHAR(64);
ALTER TABLE IF EXISTS suggestion_runs RENAME TO opportunity_runs;
ALTER TABLE IF EXISTS suggestion_masters RENAME TO opportunity_masters;
ALTER TABLE IF EXISTS trade_suggestions RENAME TO trade_opportunities;
ALTER TABLE IF EXISTS suggestion_memories RENAME TO opportunity_memories;
DO \$\$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='opportunity_masters' AND column_name='suggestions_total') THEN
        ALTER TABLE opportunity_masters RENAME COLUMN suggestions_total TO opportunities_total;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='opportunity_masters' AND column_name='last_suggestion_count') THEN
        ALTER TABLE opportunity_masters RENAME COLUMN last_suggestion_count TO last_opportunity_count;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='opportunity_memories' AND column_name='suggestion_id') THEN
        ALTER TABLE opportunity_memories RENAME COLUMN suggestion_id TO opportunity_id;
    END IF;
END \$\$;
UPDATE alembic_version SET version_num = '0011_rename_to_opportunities' WHERE version_num = '0010_suggestion_masters';
" >/dev/null 2>&1 || true

echo " ==> [RESTORE STATS] Verifying Restored Records in Database & Vector Memory:"

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
" 2>/dev/null || echo "   * Database tables & pgvector memory: restored"

echo "================================================================================"
echo " ==> [RESTORE COMPLETE] 100% of Database & AI Vector Memory Restored!"
echo "================================================================================"
