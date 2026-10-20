#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

COMPOSE_FILE="$ROOT/docker/docker-compose.yml"
POSTGRES_CONTAINER="autotrader_postgres"

echo "================================================================================"
echo " ==> [SHUTDOWN] Initiating Clean Server Shutdown & Auto DB Backup..."
echo "================================================================================"

# Perform auto backup if database container is running
if docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
    echo " ==> [AUTO-BACKUP] Creating snapshot before containers shut down..."
    if [ -f "$ROOT/backup.sh" ]; then
        "$ROOT/backup.sh" || { echo " [ERROR] Backup failed; shutdown aborted to preserve the running database."; exit 1; }
    elif [ -f "$ROOT/docker/backup.sh" ]; then
        "$ROOT/docker/backup.sh" || { echo " [ERROR] Backup failed; shutdown aborted to preserve the running database."; exit 1; }
    else
        echo " [ERROR] Backup script missing; shutdown aborted."
        exit 1
    fi
else
    echo " [INFO] Database container not active, skipping pre-shutdown backup."
fi

echo " ==> [STOPPING] Bringing down Docker containers..."
docker compose -p autotrader -f "$COMPOSE_FILE" down "$@"

echo "================================================================================"
echo " ==> [SERVER STOPPED] System shutdown complete."
echo "     Latest DB snapshot saved at: backup/latest.sql.gz"
echo "================================================================================"
