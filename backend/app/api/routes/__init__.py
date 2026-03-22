# API routes exports
from .auth import router as auth_router
from .auth import get_current_active_user, get_current_user
from .candidates import router as candidates_router
from .jobs import router as jobs_router
from .search import router as search_router
from .stats import router as stats_router
from .notes import router as notes_router
from .admin import router as admin_router

__all__ = [
    "auth_router",
    "candidates_router",
    "jobs_router",
    "search_router",
    "stats_router",
    "notes_router",
    "admin_router",
    "get_current_user",
    "get_current_active_user",
]

