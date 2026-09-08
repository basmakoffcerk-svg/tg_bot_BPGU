"""
FastAPI приложение АРМ Старосты.
"""
from contextlib import asynccontextmanager
from datetime import datetime
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import alerts, attendance, auth, reports, schedule, webhook
from app.core.config import settings
from app.core.seed import seed_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация базы данных и старосты при запуске."""
    try:
        await seed_database()
    except Exception as e:
        print(f"Lifespan seed warning: {e}")
    yield


app = FastAPI(
    title="АРМ Старосты API",
    description="REST API для Telegram Mini App группы 240326 Матинф БГПУ",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Healthchecks
@app.get("/api/v1/health")
@app.get("/api/health")
@app.get("/health")
async def healthcheck():
    return {
        "status": "healthy",
        "database": "connected",
        "telegram_bot": "active",
        "server_time": datetime.utcnow().isoformat(),
    }


# Подключение маршрутизаторов
app.include_router(auth.router, prefix="/api/v1")
app.include_router(schedule.router, prefix="/api/v1")
app.include_router(attendance.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(webhook.router, prefix="/api")
app.include_router(webhook.router)

# Статика фронтенда Mini App
webapp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "webapp")
if os.path.exists(webapp_dir):
    app.mount("/webapp", StaticFiles(directory=webapp_dir, html=True), name="webapp")

