import time
from contextlib import asynccontextmanager
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from pytz import timezone as ZoneInfo
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.core.config.settings import settings
from app.core.db.session import async_engine, async_session_factory
from app.core.exception.exception_handlers import register_exception_handlers
from app.core.logging.logger import (
    BOLD,
    BRIGHT_BLACK,
    BRIGHT_CYAN,
    BRIGHT_GREEN,
    BRIGHT_RED,
    BRIGHT_YELLOW,
    CYAN,
    GREEN,
    MAGENTA,
    RED,
    RESET,
    YELLOW,
    BRIGHT_WHITE,
    DIM,
    logger,
    setup_logging,
)
from app.core.logging.http_logger import HttpTrafficLoggingMiddleware
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import success
from app.core.scheduler.scheduler import shutdown_scheduler, start_scheduler


BANNER = rf"""
{BRIGHT_CYAN}{BOLD}
   ___         __           __                  __          
  / _ | __ __ / /_ ___  ___ / /_ ____ ___ _ ___/ /___  ____
 / __ |/ // // __// _ \/ -_) __// __// _ `// _  // -_)/ __/
/_/ |_|\_,_/ \__/ \___/\__/\__//_/   \_,_/ \_,_/ \__//_/   
{RESET}{BRIGHT_BLACK}────────────────────────────────────────────────────────────────────────{RESET}
 {BRIGHT_WHITE}Auto-Trader Unified High-Frequency Trading Core{RESET}
 • {DIM}Environment:{RESET}  {BRIGHT_GREEN}{settings.APP_ENV}{RESET}
 • {DIM}Worker Mode:{RESET}  {BRIGHT_CYAN}Single Uvicorn Worker (PID bound){RESET}
 • {DIM}Scheduler:{RESET}    {BRIGHT_YELLOW}APScheduler (Timezone: {settings.SCHEDULER_TIMEZONE}){RESET}
 • {DIM}Encryption:{RESET}   {BRIGHT_GREEN}AES-GCM Master Key Loaded{RESET}
{BRIGHT_BLACK}────────────────────────────────────────────────────────────────────────{RESET}
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Runs on single uvicorn worker.
    """
    setup_logging()
    print(BANNER)
    logger.info(f"Booting {settings.APP_NAME} in [{settings.APP_ENV}] mode...")

    # 1. Verify DB connection
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        logger.info(f"{BRIGHT_GREEN}PostgreSQL & pgvector connection established successfully.{RESET}")
    except Exception as e:
        logger.error(f"Database connection check warning: {e}")

    # 2. Start scheduler
    start_scheduler()
    logger.info(f"{BRIGHT_YELLOW}APScheduler started with timezone {settings.SCHEDULER_TIMEZONE}.{RESET}")

    yield

    # Shutdown sequence
    logger.info("Initiating graceful shutdown sequence...")
    shutdown_scheduler()
    await async_engine.dispose()
    logger.info("Database connection pools disposed. Shutdown clean.")


def create_application() -> FastAPI:
    """FastAPI Application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global unified exception handling
    register_exception_handlers(app)

    # Detailed HTTP Traffic Logger (Request & Response with Headers, Body & Timing)
    app.add_middleware(HttpTrafficLoggingMiddleware)

    # Base & Healthcheck Routes
    @app.get(
        "/health",
        include_in_schema=False,
    )
    @app.get(
        "/api/v1/health",
        response_model=ApiResponse[dict],
        status_code=status.HTTP_200_OK,
        tags=["System"],
    )
    async def health_check():
        """Universal healthcheck returning standard ApiResponse envelope."""
        db_connected = False
        vector_available = False
        try:
            async with async_session_factory() as session:
                res = await session.execute(text("SELECT 1"))
                if res.scalar() == 1:
                    db_connected = True
                ext_res = await session.execute(
                    text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
                )
                if ext_res.scalar() == 1:
                    vector_available = True
        except Exception:
            db_connected = False

        tz = ZoneInfo(settings.SCHEDULER_TIMEZONE)
        now_local = datetime.now(tz).isoformat()

        health_data = {
            "status": "healthy" if db_connected else "degraded",
            "environment": settings.APP_ENV,
            "timestamp": now_local,
            "timezone": settings.SCHEDULER_TIMEZONE,
            "database": {
                "connected": db_connected,
                "pgvector": vector_available,
            },
        }

        return success(data=health_data, message="System is operational")

    # Feature Module Routers
    from app.modules.users.controller import oauth_router, user_router
    from app.modules.strategies.controller import (
        strategy_router,
        rule_router,
    )
    app.include_router(user_router, prefix=settings.API_V1_PREFIX)
    app.include_router(oauth_router, prefix=settings.API_V1_PREFIX)

    app.include_router(strategy_router, prefix=settings.API_V1_PREFIX)
    app.include_router(rule_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()
