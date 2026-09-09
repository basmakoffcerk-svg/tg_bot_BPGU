from bot.handlers.commands import router as commands_router
from bot.handlers.grid_chat import chat_grid_router
from bot.handlers.onboarding import router as onboarding_router
from bot.handlers.schedule_upload import schedule_upload_router

__all__ = ["commands_router", "onboarding_router", "schedule_upload_router", "chat_grid_router"]

