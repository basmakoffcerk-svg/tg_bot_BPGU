import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.routes import (
    alerts_router,
    attendance_router,
    auth_router,
    health_router,
    reports_router,
    schedule_router,
)
from core.config import settings
from core.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database tables are created
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: Clean up resources
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="АРМ Старосты — API (Группа 240326 «Матинф» БГПУ)",
        description="Высокопроизводительный бэкенд для Telegram Mini App учета посещаемости и управления группой.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS configuration
    origins = ["*"] if settings.FRONTEND_URL == "*" else [settings.FRONTEND_URL, "https://web.telegram.org"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global RFC 7807 Exception Handlers
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            return JSONResponse(status_code=exc.status_code, content=detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": f"https://errors.starosta.app/http-{exc.status_code}",
                "title": "HTTP Error",
                "status": exc.status_code,
                "detail": str(detail),
                "instance": str(request.url.path),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "type": "https://errors.starosta.app/validation-error",
                "title": "Ошибка валидации входных данных",
                "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "detail": exc.errors(),
                "instance": str(request.url.path),
            },
        )

    # Register API v1 Routers
    api_v1_prefix = "/api/v1"
    app.include_router(health_router, prefix=api_v1_prefix)
    app.include_router(auth_router, prefix=api_v1_prefix)
    app.include_router(schedule_router, prefix=api_v1_prefix)
    app.include_router(attendance_router, prefix=api_v1_prefix)
    app.include_router(alerts_router, prefix=api_v1_prefix)
    app.include_router(reports_router, prefix=api_v1_prefix)

    # Mount Telegram Mini App Static Files
    webapp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp")
    if os.path.exists(webapp_dir):
        app.mount("/webapp", StaticFiles(directory=webapp_dir, html=True), name="webapp")
        app.mount("/app", StaticFiles(directory=webapp_dir, html=True), name="app")
        app.mount("/", StaticFiles(directory=webapp_dir, html=True), name="root_webapp")

    return app


app = create_app()
