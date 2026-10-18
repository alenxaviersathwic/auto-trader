from contextlib import asynccontextmanager
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from pytz import timezone as ZoneInfo
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.core.config.settings import settings
from app.core.db.session import async_engine, async_session_factory
from app.core.exception.exception_handlers import register_exception_handlers
from app.core.logging.logger import logger, setup_logging
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import success
from app.core.scheduler.scheduler import shutdown_scheduler, start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Runs on single uvicorn worker.
    """
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} in [{settings.APP_ENV}] mode...")

    # 1. Verify DB connection
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        logger.info("Database connection successfully established.")
    except Exception as e:
        logger.error(f"Database connection check warning: {e}")

    # 2. Start scheduler
    start_scheduler()

    yield

    # Shutdown sequence
    logger.info("Shutting down application...")
    shutdown_scheduler()
    await async_engine.dispose()
    logger.info("Database engine disposed. Shutdown complete.")


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

    # Base & Healthcheck Routes
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
                # Check pgvector extension
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
    app.include_router(user_router, prefix=settings.API_V1_PREFIX)
    app.include_router(oauth_router, prefix=settings.API_V1_PREFIX)
    app.include_router(oauth_router)

    return app


app = create_application()
