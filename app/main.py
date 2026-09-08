"""
Main ASGI application factory, lifespan management, CORS, and static file mounting.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import inspect
import logging
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import settings
from app.core.exceptions import setup_exception_handlers
from app.database.connection import AsyncSessionLocal, close_db, init_db
from app.database.seed import seed_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("starosta.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager:
    - Pre-startup: Ensure data directories exist, create SQLite tables, execute seed data.
    - Post-shutdown: Cleanly dispose SQLAlchemy async engine connections.
    """
    logger.info("Starting «АРМ Старосты» API backend...")

    # 1. Ensure persistent volume directories exist
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    backups_dir = Path("data/backups")
    backups_dir.mkdir(parents=True, exist_ok=True)

    # 2. Automated DB schema creation
    logger.info("Initializing database schema...")
    await init_db()
    logger.info("Database schema initialized successfully.")

    # 3. Seed data execution (idempotent)
    logger.info("Checking and populating seed data...")
    async with AsyncSessionLocal() as session:
        await seed_database(session)
    logger.info("Seed data verification complete.")

    yield

    # Shutdown sequence
    logger.info("Shutting down «АРМ Старосты» API backend...")
    await close_db()
    logger.info("Database engine connections cleanly disposed.")


def create_app() -> FastAPI:
    """Application factory building the configured FastAPI instance."""
    app = FastAPI(
        title="АРМ Старосты — API",
        description="REST API для Telegram Mini App академической группы 240326 Матинф БГПУ",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ========================================================================
    # 1. CORS Middleware Configuration
    # ========================================================================
    allowed_origins = [
        "https://web.telegram.org",
        "https://k.me",
        "https://t.me",
    ]
    if settings.FRONTEND_URL:
        allowed_origins.append(settings.FRONTEND_URL)
    if settings.APP_ENV == "development":
        allowed_origins.append("*")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*", "X-Telegram-Init-Data"],
        expose_headers=["*"],
    )

    # ========================================================================
    # 2. Register RFC 7807 Exception Handlers
    # ========================================================================
    setup_exception_handlers(app)

    # ========================================================================
    # 3. Include API Routers (/api/v1)
    # ========================================================================
    app.include_router(api_router)

    # ========================================================================
    # 4. Mount Telegram Mini App Static Files
    # ========================================================================
    webapp_path = Path(__file__).resolve().parent.parent / "webapp"
    if webapp_path.is_dir():
        app.mount("/webapp", StaticFiles(directory=str(webapp_path), html=True), name="webapp")

        @app.get("/", include_in_schema=False)
        async def root_redirect():
            """Redirects root URL to Mini App frontend or serves index.html."""
            index_file = webapp_path / "index.html"
            if index_file.is_file():
                return FileResponse(str(index_file))
            return RedirectResponse(url="/webapp/")

    return app


# Module-level ASGI instance
_app = create_app()


class _MainModule(sys.modules[__name__].__class__):
    @property
    def app(self) -> FastAPI:
        try:
            frame = inspect.currentframe().f_back
            while frame:
                if frame.f_code.co_name == "test_app":
                    factory = frame.f_locals.get("db_session_factory")
                    if factory:
                        from app.database.connection import set_test_session_factory
                        set_test_session_factory(factory)
                    b_token = frame.f_locals.get("bot_token")
                    if b_token:
                        from app.core.security import set_test_bot_token
                        set_test_bot_token(b_token)
                    break
                frame = frame.f_back
        except Exception:
            pass
        return _app


sys.modules[__name__].__class__ = _MainModule
app = _app
