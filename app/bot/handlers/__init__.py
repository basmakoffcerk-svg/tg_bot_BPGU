from app.bot.handlers.common import router as common_router
from app.bot.handlers.admin import router as admin_router
from app.bot.handlers.import_export import router as import_export_router
from app.bot.handlers.broadcast import router as broadcast_router
from app.bot.handlers.student import router as student_router

__all__ = [
    "common_router",
    "admin_router",
    "import_export_router",
    "broadcast_router",
    "student_router",
]
