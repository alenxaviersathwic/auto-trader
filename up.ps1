# ==============================================================================
# auto-trader Unified Startup & Auto-Backup Script (PowerShell)
# ==============================================================================
# 1. Builds backend and frontend production images
# 2. Starts PostgreSQL with pgvector and restores latest backup if available
# 3. Boots all services via Docker Compose
# 4. Traps Ctrl+C / termination to automatically dump database & pgvector to backup/
# ==============================================================================

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$ComposeFile = "docker/docker-compose.yml"
$BackupDir = "backup"
$PostgresContainer = "autotrader_postgres"
$DbUser = "autotrader"
$DbName = "autotrader"

if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "   Starting auto-trader System (Production Build & Run)         " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

function Perform-BackupAndShutdown {
    Write-Host ""
    Write-Host "=================================================================" -ForegroundColor Yellow
    Write-Host " [Termination / Exit Detected] Initiating Auto-Backup...         " -ForegroundColor Yellow
    Write-Host "=================================================================" -ForegroundColor Yellow

    $running = docker ps --format '{{.Names}}' | Select-String "^$PostgresContainer$"
    if ($running) {
        $timestamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
        $backupFile = "$BackupDir/autotrader_backup_$timestamp.sql"
        $latestFile = "$BackupDir/latest.sql"

        Write-Host "[BACKUP] Exporting database, pgvector embeddings, and tables..." -ForegroundColor Green
        docker exec -t $PostgresContainer pg_dump -U $DbUser -d $DbName --clean --if-exists --no-owner --no-privileges | Out-File -Encoding utf8 $backupFile
        Copy-Item -Path $backupFile -Destination $latestFile -Force

        Write-Host "[BACKUP SUCCESS] Data safely saved to:" -ForegroundColor Green
        Write-Host "   -> $backupFile"
        Write-Host "   -> $latestFile"
    } else {
        Write-Host "[BACKUP WARNING] PostgreSQL container is not running; skipping backup." -ForegroundColor Yellow
    }

    Write-Host "[SHUTDOWN] Stopping all containers..." -ForegroundColor Cyan
    docker compose -f $ComposeFile down
    Write-Host "=================================================================" -ForegroundColor Cyan
    Write-Host "   auto-trader stopped cleanly.                                 " -ForegroundColor Cyan
    Write-Host "=================================================================" -ForegroundColor Cyan
}

try {
    # Step 1: Build production containers
    Write-Host "[BUILD] Building backend and frontend production containers..." -ForegroundColor Green
    docker compose -f $ComposeFile build

    # Step 2: Start PostgreSQL first
    Write-Host "[DATABASE] Starting PostgreSQL with pgvector..." -ForegroundColor Green
    docker compose -f $ComposeFile up -d postgres

    Write-Host "[DATABASE] Waiting for PostgreSQL to be healthy..." -ForegroundColor Yellow
    do {
        Start-Sleep -Seconds 1
        $ready = docker exec $PostgresContainer pg_isready -U $DbUser -d $DbName 2>&1
    } until ($LASTEXITCODE -eq 0)
    Write-Host "[DATABASE] PostgreSQL is online and ready." -ForegroundColor Green

    # Step 3: Check for existing backup and restore
    $latestBackup = "$BackupDir/latest.sql"
    if (Test-Path $latestBackup) {
        Write-Host "[RESTORE] Found existing database backup: $latestBackup" -ForegroundColor Green
        Write-Host "[RESTORE] Restoring tables, data, and pgvector embeddings..." -ForegroundColor Green
        Get-Content $latestBackup | docker exec -i $PostgresContainer psql -U $DbUser -d $DbName
        Write-Host "[RESTORE SUCCESS] Database restored from $latestBackup." -ForegroundColor Green
    } else {
        Write-Host "[DATABASE] No previous backup found. Initializing clean database." -ForegroundColor Yellow
    }

    # Ensure vector extension is enabled
    docker exec -i $PostgresContainer psql -U $DbUser -d $DbName -c "CREATE EXTENSION IF NOT EXISTS vector;" | Out-Null

    # Step 4: Start full project
    Write-Host "=================================================================" -ForegroundColor Cyan
    Write-Host "   Launching all services (Frontend, Backend, PostgreSQL)       " -ForegroundColor Cyan
    Write-Host "   Press Ctrl+C at any time to automatically back up and exit.  " -ForegroundColor Cyan
    Write-Host "=================================================================" -ForegroundColor Cyan
    docker compose -f $ComposeFile up
}
finally {
    Perform-BackupAndShutdown
}
