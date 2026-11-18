"""Rate limiting (slowapi). In-memory storage: correct for a single API instance.

Behind a hosting proxy, run uvicorn with --proxy-headers so the client IP (not the
proxy's) is used as the key.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.errors import error_response

limiter = Limiter(key_func=get_remote_address, headers_enabled=False)


def login_limit() -> str:
    return get_settings().login_rate_limit


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return error_response(
        request,
        429,
        "Too many login attempts. Please wait a minute and try again.",
        code="rate_limited",
        headers={"Retry-After": "60"},
    )


def install_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
