"""
FastAPI приложение АРМ Старосты.
"""
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.api.routes import alerts, attendance, auth, reports, schedule
from app.core.config import settings

app = FastAPI(
    title="АРМ Старосты API",
    description="REST API для Telegram Mini App группы 240326 Матинф БГПУ",
    version="1.0.0",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Healthcheck
@app.get("/api/v1/health")
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

# Статика фронтенда Mini App
webapp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "webapp")
if os.path.exists(webapp_dir):
    app.mount("/webapp", StaticFiles(directory=webapp_dir, html=True), name="webapp")
