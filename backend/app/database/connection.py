"""SQLAlchemy engine, session factory, per-request session dependency and a health ping.

The engine is created lazily on first use, so importing the app never opens a connection
and a database outage cannot stop the API from starting (``/health`` reports it instead).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    url = settings.database_url.get_secret_value()
    connect_args: dict[str, object] = {}
    if url.startswith("mysql"):
        connect_args["connect_timeout"] = 5
    if settings.db_ssl_ca:
        # Managed cloud MySQL: verify the server certificate against the provider's CA.
        connect_args["ssl"] = {"ca": settings.db_ssl_ca}
    return create_engine(
        url,
        pool_pre_ping=True,  # drop connections the server closed while idle
        pool_recycle=280,  # stay under typical cloud idle timeouts
        connect_args=connect_args,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed (rolled back on error)."""
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ping_database() -> tuple[bool, str | None]:
    """Run ``SELECT 1``. Returns (ok, error_class_name) without leaking connection details."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        logger.warning("Database ping failed", extra={"error": type(exc).__name__})
        return False, type(exc).__name__
