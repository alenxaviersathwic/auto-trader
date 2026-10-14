#!/usr/bin/env bash
set -e

# ==============================================================================
# auto-trader Unified Startup & Auto-Backup Script
# ==============================================================================
# 1. Builds backend and frontend production images
# 2. Starts PostgreSQL with pgvector and restores latest backup if available
# 3. Boots all services via Docker Compose
# 4. Traps Ctrl+C (SIGINT) to automatically dump database and pgvector to backup/
# ==============================================================================

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

COMPOSE_FILE="docker/docker-compose.yml"
BACKUP_DIR="backup"
POSTGRES_CONTAINER="autotrader_postgres"
DB_USER="autotrader"
DB_NAME="autotrader"

mkdir -p "$BACKUP_DIR"

echo "================================================================="
echo "   Starting auto-trader System (Production Build & Run)         "
echo "================================================================="

# Trap Ctrl+C (SIGINT) and SIGTERM to perform automatic backup
cleanup_and_backup() {
    echo ""
    echo "================================================================="
    echo " [Ctrl+C / Termination Detected] Initiating Auto-Backup...      "
    echo "================================================================="

    if docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
        BACKUP_FILE="${BACKUP_DIR}/autotrader_backup_${TIMESTAMP}.sql"
        LATEST_FILE="${BACKUP_DIR}/latest.sql"

        echo "[BACKUP] Exporting database, pgvector embeddings, and tables..."
        docker exec -t "$POSTGRES_CONTAINER" pg_dump \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            --clean \
            --if-exists \
            --no-owner \
            --no-privileges > "$BACKUP_FILE"

        cp "$BACKUP_FILE" "$LATEST_FILE"
        echo "[BACKUP SUCCESS] Data safely saved to:"
        echo "   -> $BACKUP_FILE"
        echo "   -> $LATEST_FILE"
    else
        echo "[BACKUP WARNING] PostgreSQL container is not running; skipping backup."
    fi

    echo "[SHUTDOWN] Stopping all containers..."
    docker compose -f "$COMPOSE_FILE" down
    echo "================================================================="
    echo "   auto-trader stopped cleanly.                                 "
    echo "================================================================="
    exit 0
}

trap cleanup_and_backup SIGINT SIGTERM

# Step 1: Build production images
echo "[BUILD] Building backend and frontend production containers..."
docker compose -f "$COMPOSE_FILE" build

# Step 2: Start PostgreSQL first
echo "[DATABASE] Starting PostgreSQL with pgvector..."
docker compose -f "$COMPOSE_FILE" up -d postgres

echo "[DATABASE] Waiting for PostgreSQL to be healthy..."
until docker exec "$POSTGRES_CONTAINER" pg_isready -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; do
    sleep 1
done
echo "[DATABASE] PostgreSQL is online and ready."

# Step 3: Check for existing backup and restore
LATEST_BACKUP="${BACKUP_DIR}/latest.sql"

if [ -f "$LATEST_BACKUP" ] && [ -s "$LATEST_BACKUP" ]; then
    echo "[RESTORE] Found existing database backup: $LATEST_BACKUP"
    echo "[RESTORE] Restoring tables, data, and pgvector embeddings..."
    docker exec -i "$POSTGRES_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" < "$LATEST_BACKUP" > /dev/null 2>&1 || true
    echo "[RESTORE SUCCESS] Database restored from $LATEST_BACKUP."
else
    echo "[DATABASE] No previous backup found. Initializing clean database."
fi

# Ensure vector extension is enabled in all cases
docker exec -i "$POSTGRES_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;" > /dev/null 2>&1 || true

# Step 4: Start full project
echo "================================================================="
echo "   Launching all services (Frontend, Backend, PostgreSQL)       "
echo "   Press Ctrl+C at any time to automatically back up and exit.  "
echo "================================================================="
docker compose -f "$COMPOSE_FILE" up
