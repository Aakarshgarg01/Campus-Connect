"""GET /health: reports API, database and model status.

Returns 200 only when the database answers and every stage model is loaded; otherwise 503,
with the same body, so a host's health check never marks a half-working deploy as healthy.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.database.connection import ping_database

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service health (API, database, models)")
def health(request: Request) -> JSONResponse:
    db_ok, db_error = ping_database()
    registry = request.app.state.models
    healthy = db_ok and registry.all_loaded
    body = {
        "status": "ok" if healthy else "degraded",
        "service": request.app.title,
        "version": request.app.version,
        "database": {"connected": db_ok, **({"error": db_error} if db_error else {})},
        "models": registry.status(),
    }
    return JSONResponse(status_code=200 if healthy else 503, content=body)
