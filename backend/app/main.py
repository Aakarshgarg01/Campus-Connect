"""FastAPI application entry point.

Run locally:  uvicorn app.main:app --reload --port 8000   (from the backend/ folder)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import REQUEST_ID_HEADER, install_error_handling
from app.core.logging import configure_logging
from app.core.rate_limit import install_rate_limiting
from app.ml.model_loader import load_models
from app.routers import academic_routes, auth_routes, health_routes, prediction_routes, student_routes

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Load the ML pipelines once per process, never per request.
        app.state.models = load_models(settings.model_dir)
        logger.info(
            "Startup complete",
            extra={"environment": settings.environment, "models": app.state.models.status()},
        )
        yield

    app = FastAPI(
        title=settings.app_name,
        version="0.9.0",
        description="Predicts final exam performance from attendance, internal tests and assignments, "
        "with SHAP explanations. Predictions are estimates, not guaranteed results.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,  # exact origins from env; never "*" with credentials
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    install_error_handling(app)
    install_rate_limiting(app)
    app.include_router(health_routes.router)
    app.include_router(auth_routes.router)
    app.include_router(student_routes.router)
    app.include_router(prediction_routes.router)
    app.include_router(prediction_routes.info_router)
    app.include_router(academic_routes.router)
    return app


app = create_app()
