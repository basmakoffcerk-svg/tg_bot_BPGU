"""
API package: dependencies, router, and endpoints.
"""
from app.api.deps import (
    get_current_active_student,
    get_current_telegram_user,
    get_current_user,
    get_db,
    get_validated_init_data,
    require_roles,
    require_starosta,
    require_zam_or_starosta,
)
from app.api.router import api_router

__all__ = [
    "api_router",
    "get_db",
    "get_validated_init_data",
    "get_current_telegram_user",
    "get_current_user",
    "get_current_active_student",
    "require_roles",
    "require_zam_or_starosta",
    "require_starosta",
]
