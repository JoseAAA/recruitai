"""
Rate limiting utilities using slowapi.
Provides a shared limiter instance and decorators for route protection.
"""
import logging

logger = logging.getLogger(__name__)

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    _limiter = Limiter(key_func=get_remote_address)
    RATE_LIMIT_AVAILABLE = True
except ImportError:
    _limiter = None
    RATE_LIMIT_AVAILABLE = False
    logger.warning("slowapi not installed — rate limiting unavailable")


def get_limiter():
    """Return the shared limiter instance (or None if unavailable)."""
    return _limiter


def limit(rate: str):
    """
    Decorator that applies rate limiting if slowapi is available.
    Falls back to a no-op if not installed.

    Usage:
        @router.post("/login")
        @limit("10/minute")
        async def login(request: Request, ...):
    """
    if RATE_LIMIT_AVAILABLE and _limiter is not None:
        return _limiter.limit(rate)

    # No-op decorator when slowapi is not available
    def noop(func):
        return func
    return noop
