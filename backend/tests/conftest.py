"""Shared fixtures.

* make_client: a fresh app per test with its own settings (env vars override backend/.env).
* mysql_url / engine: the real MySQL test database (TEST_DATABASE_URL), migrated with Alembic.
* api: a client wired to the MySQL test database; all tables are emptied after each test.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterator
from pathlib import Path

import joblib
import pandas as pd
import pytest
import sklearn
from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.database.connection import get_engine, get_session_factory
from app.ml.features import STAGE_FEATURES
from app.ml.model_loader import STAGES
from app.models import Base

BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEST_SECRET = "test-secret-" + "x" * 40
FRONTEND = "http://localhost:5173"
# Nothing listens on port 1, so this always fails to connect (quickly).
UNREACHABLE_MYSQL = "mysql+pymysql://nobody:nothing@127.0.0.1:1/student_predictor"


def _clear_caches() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest.fixture
def make_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def _make(database_url: str = "sqlite://", model_dir: Path | None = None, **env: str) -> TestClient:
        # Environment variables take precedence over backend/.env, so a developer's .env
        # cannot change these values; DB_SSL_CA is cleared explicitly for the same reason.
        monkeypatch.setenv("DB_SSL_CA", "")
        monkeypatch.setenv("DATABASE_URL", database_url)
        monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
        monkeypatch.setenv("CORS_ORIGINS", FRONTEND)
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setenv("LOGIN_RATE_LIMIT", "5/minute")
        monkeypatch.setenv("MODEL_DIR", str(model_dir or tmp_path / "empty_models"))
        for key, value in env.items():
            monkeypatch.setenv(key.upper(), value)
        _clear_caches()
        limiter.reset()
        from app.main import create_app

        client = TestClient(create_app(), raise_server_exceptions=False)
        client.__enter__()  # runs the lifespan (model loading)
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.__exit__(None, None, None)
    get_engine().dispose() if get_engine.cache_info().currsize else None
    _clear_caches()


@pytest.fixture
def model_dir(tmp_path: Path) -> Path:
    """A real (tiny) fitted sklearn pipeline per stage, to exercise the loader end to end."""
    root = tmp_path / "models"
    for stage in STAGES:
        stage_dir = root / stage
        stage_dir.mkdir(parents=True)
        features = STAGE_FEATURES[stage]
        frame = pd.DataFrame([[0.0] * len(features), [100.0] * len(features)], columns=features)
        pipeline = Pipeline([("model", LinearRegression())]).fit(frame, [0.0, 100.0])
        joblib.dump(pipeline, stage_dir / "model.joblib")
        metadata = {
            "model_version": f"{stage}-test",
            "features": [{"name": f} for f in features],
            "library_versions": {"scikit-learn": sklearn.__version__},
            "model_sha256": hashlib.sha256((stage_dir / "model.joblib").read_bytes()).hexdigest(),
        }
        (stage_dir / "metadata.json").write_text(json.dumps(metadata))
    return root


# --- real MySQL ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def mysql_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(BACKEND_ROOT / ".env").get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    if "_test" not in url.rsplit("/", 1)[-1]:
        pytest.fail("TEST_DATABASE_URL must point at a database whose name contains '_test'")
    return url


@pytest.fixture(scope="session")
def engine(mysql_url: str) -> Iterator[Engine]:
    engine = create_engine(mysql_url, pool_pre_ping=True)
    try:
        engine.connect().close()
    except DBAPIError as exc:
        pytest.skip(f"MySQL test database unreachable: {type(exc).__name__}")
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        command.upgrade(config, "head")
    yield engine
    engine.dispose()


def empty_all_tables(engine: Engine) -> None:
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):  # children before parents
            connection.execute(text(f"DELETE FROM {table.name}"))


@pytest.fixture
def api(make_client, mysql_url: str, engine: Engine, model_dir: Path) -> Iterator[TestClient]:
    client = make_client(database_url=mysql_url, model_dir=model_dir)
    yield client
    empty_all_tables(engine)


REAL_MODELS = BACKEND_ROOT / "models_store"


@pytest.fixture
def api_real(make_client, mysql_url: str, engine: Engine) -> Iterator[TestClient]:
    """Like `api`, but loads the real trained pipelines from models_store/."""
    client = make_client(database_url=mysql_url, model_dir=REAL_MODELS)
    yield client
    empty_all_tables(engine)
