from api.routes.alerts import router as alerts_router
from api.routes.attendance import router as attendance_router
from api.routes.auth import router as auth_router
from api.routes.health import router as health_router
from api.routes.reports import router as reports_router
from api.routes.schedule import router as schedule_router

__all__ = [
    "alerts_router",
    "attendance_router",
    "auth_router",
    "health_router",
    "reports_router",
    "schedule_router",
]
