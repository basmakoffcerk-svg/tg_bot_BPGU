"""
Central APIRouter consolidating all v1 endpoint sub-routers.
"""
from fastapi import APIRouter

from app.api.endpoints import alerts, auth, attendance, health, reports, schedule

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router, prefix="/health", tags=["Telemetry & Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Profile"])
api_router.include_router(schedule.router, prefix="/schedule", tags=["Academic Timetable"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["Attendance & Geocheckin"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Emergency Broadcasts"])
api_router.include_router(reports.router, prefix="/reports", tags=["Dean Reports"])
