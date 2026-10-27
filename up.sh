#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

COMPOSE_FILE="$ROOT/docker/docker-compose.yml"
BACKUP_DIR="$ROOT/backup"
POSTGRES_CONTAINER="autotrader_postgres"
DB_USER="autotrader"
DB_NAME="autotrader"

echo "================================================================================"
echo " ==> [PRE-FLIGHT] Checking Required Daemons (Docker & Ollama)..."
echo "================================================================================"

# 1. Docker Daemon Pre-flight & Auto-launch
if ! docker info >/dev/null 2>&1; then
    echo " [INFO] Docker daemon is not running. Launching Docker Desktop..."
    if command -v open >/dev/null 2>&1; then
        open -g -a Docker 2>/dev/null || open -g -a "Docker Desktop" 2>/dev/null || true
    fi

    echo -n " [WAIT] Waiting for Docker daemon to become ready..."
    DOCKER_READY=false
    for i in $(seq 1 60); do
        if docker info >/dev/null 2>&1; then
            DOCKER_READY=true
            echo " Ready!"
            break
        fi
        echo -n "."
        sleep 1
    done

    if [ "$DOCKER_READY" != true ]; then
        echo ""
        echo " [ERROR] Docker daemon did not start within 60s. Please start Docker manually."
        exit 1
    fi
else
    echo " [OK] Docker daemon is active and responsive."
fi

# 2. Ollama AI Service Pre-flight & Auto-launch
if ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo " [INFO] Ollama service is not running. Starting Ollama daemon..."
    if command -v ollama >/dev/null 2>&1; then
        ollama serve >/dev/null 2>&1 &
    elif command -v open >/dev/null 2>&1; then
        open -g -a Ollama 2>/dev/null || true
    fi

    echo -n " [WAIT] Waiting for Ollama (http://localhost:11434) to become ready..."
    OLLAMA_READY=false
    for i in $(seq 1 30); do
        if curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
            OLLAMA_READY=true
            echo " Ready!"
            break
        fi
        echo -n "."
        sleep 1
    done

    if [ "$OLLAMA_READY" != true ]; then
        echo ""
        echo " [WARN] Ollama could not be started automatically. Local AI features may be degraded."
    else
        echo " [OK] Ollama AI server is active and responsive."
    fi
else
    echo " [OK] Ollama AI server is active and responsive."
fi

# Verify Qwen model on host Ollama
if curl -fsS http://localhost:11434/api/tags 2>/dev/null | grep -q "qwen"; then
    echo " [OK] Ollama Qwen model is ready on host system."
else
    echo " [INFO] Downloading Qwen model (qwen3:8b) into Ollama..."
    ollama pull qwen3:8b || true
fi

echo ""
echo "================================================================================"
echo " ==> [BUILD] Compiling Backend & Frontend Bundles..."
echo "================================================================================"

# Stop and remove conflicting containers by name so Docker Compose can recreate them cleanly
for c in autotrader_backend autotrader_frontend; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${c}$"; then
        echo "     Removing conflicting $c container..."
        docker rm -f "$c" >/dev/null 2>&1 || true
    fi
done

# Clean up any stale autotrader_postgres container if not attached to current project
if docker ps -a --format '{{.Names}}' | grep -q "^autotrader_postgres$"; then
    if ! docker compose -p autotrader -f "$COMPOSE_FILE" ps postgres --format '{{.Names}}' 2>/dev/null | grep -q "^autotrader_postgres$"; then
        echo "     Resolving stale autotrader_postgres container..."
        docker rm -f autotrader_postgres >/dev/null 2>&1 || true
    fi
fi

# 1. Build Backend container
echo " ==> [1/2] Building auto-trader Backend Container (FastAPI + Alembic)..."
docker compose -p autotrader -f "$COMPOSE_FILE" build backend

# 2. Build Frontend container (and optional host Vite build if node_modules exists)
echo " ==> [2/2] Building auto-trader Frontend Container (React Vite SPA + Nginx)..."
if command -v xattr >/dev/null 2>&1 && [ -d "$ROOT/frontend/node_modules" ]; then
    xattr -r -d com.apple.quarantine "$ROOT/frontend/node_modules" >/dev/null 2>&1 || true
fi
if [ -d "$ROOT/frontend/node_modules" ]; then
    (cd "$ROOT/frontend" && npm run build)
elif [ ! -f "$ROOT/frontend/dist/index.html" ]; then
    (cd "$ROOT/frontend" && npm install && npm run build)
fi
docker compose -p autotrader -f "$COMPOSE_FILE" build frontend

mkdir -p "$BACKUP_DIR" "$ROOT/logs"

# Check if detached mode requested (-d or --detach)
DETACHED=false
for arg in "$@"; do
    if [ "$arg" == "-d" ] || [ "$arg" == "--detach" ]; then
        DETACHED=true
        break
    fi
done

# Step 3: Boot PostgreSQL first and restore latest backup if database is uninitialized
echo ""
echo " ==> [DATABASE] Starting PostgreSQL with pgvector..."
docker compose -p autotrader -f "$COMPOSE_FILE" up -d postgres

echo -n " ==> [WAIT] Waiting for PostgreSQL (${POSTGRES_CONTAINER}) to be ready..."
until docker exec "$POSTGRES_CONTAINER" pg_isready -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo " Ready!"

# Ensure vector extension is present
docker exec "$POSTGRES_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;" > /dev/null 2>&1 || true

# Check if tables exist; if not, restore latest backup
HAS_USERS_TABLE=$(docker exec "$POSTGRES_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -A -c "SELECT to_regclass('public.users');" 2>/dev/null || echo "")
if [ -z "$HAS_USERS_TABLE" ] || [ "$HAS_USERS_TABLE" = "" ]; then
    if [ -f "$ROOT/restore.sh" ] && ([ -f "$BACKUP_DIR/latest.sql.gz" ] || [ -f "$BACKUP_DIR/latest.sql" ]); then
        echo " ==> [RESTORE] Fresh database detected. Restoring snapshot from backup/..."
        "$ROOT/restore.sh" || echo " [WARN] Database restore completed with warnings."
    fi
fi

echo ""
echo "================================================================================"
echo " ==> [SERVICES INITIALIZED & RUNNING]"
echo "================================================================================"
echo "   * Frontend UI (Production):  http://localhost:${FRONTEND_PORT:-3001}/   (Path: $ROOT/frontend)"
echo "   * Frontend UI (Vite Dev):    http://localhost:5173/           (Path: $ROOT/frontend)"
echo "   * Backend REST API:          http://localhost:${PORT:-8000}/api/v1 (Path: $ROOT/backend-service)"
echo "   * Backend Swagger Docs:      http://localhost:${PORT:-8000}/docs"
echo "   * Backend Health Check:      http://localhost:${PORT:-8000}/health"
echo "   * PostgreSQL Database:       localhost:${POSTGRES_PORT:-5432} (DB: ${POSTGRES_DB:-autotrader})"
echo "================================================================================"
echo ""

if [ "$DETACHED" = true ]; then
    echo "==> Starting Docker Compose in detached mode..."
    docker compose -p autotrader -f "$COMPOSE_FILE" up -d "$@"
    echo "==> System is running in background. Use ./down.sh to stop and auto-backup."
    exit 0
fi

# Cleanup and Auto-Backup Trap on Ctrl+C (SIGINT) or SIGTERM
cleanup() {
    echo ""
    echo "================================================================================"
    echo " ==> [AUTO-BACKUP] Ctrl+C detected! Backing up database before stopping..."
    echo "================================================================================"
    if [ -f "$ROOT/backup.sh" ]; then
        "$ROOT/backup.sh" || echo " [WARN] Pre-shutdown backup completed with warnings."
    elif [ -f "$ROOT/docker/backup.sh" ]; then
        "$ROOT/docker/backup.sh" || echo " [WARN] Pre-shutdown backup completed with warnings."
    fi
    echo ""
    echo " ==> [STOPPING] Bringing down Docker containers..."
    docker compose -p autotrader -f "$COMPOSE_FILE" down > /dev/null 2>&1 || true
    echo "================================================================================"
    echo " ==> [SERVER STOPPED] All data & AI memory saved to:"
    echo "     backup/latest.sql.gz"
    echo "================================================================================"
    exit 0
}

trap cleanup INT TERM

echo "==> Starting Docker Compose..."
docker compose -p autotrader -f "$COMPOSE_FILE" up -d "$@"

echo "==> Streaming live logs (Press Ctrl+C anytime to stop and auto-backup)..."
docker compose -p autotrader -f "$COMPOSE_FILE" logs -f &
LOGS_PID=$!

wait "$LOGS_PID" 2>/dev/null || cleanup
