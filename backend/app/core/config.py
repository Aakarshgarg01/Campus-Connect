"""Application configuration loaded from environment variables and backend/.env.

Every secret (database password, JWT secret) comes from the environment. Nothing
sensitive has a default value, so the app refuses to start if one is missing.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    app_name: str = "Student Performance Predictor API"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # Database: a full SQLAlchemy URL, e.g. mysql+pymysql://user:pass@host:3306/student_predictor
    database_url: SecretStr
    # Path to a CA bundle for managed cloud MySQL. Empty means no TLS (local only).
    db_ssl_ca: str | None = None

    # Auth
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=60, gt=0)
    login_rate_limit: str = "5/minute"
    # The JWT is returned in the login body (Swagger/Postman) and also set as an httpOnly cookie
    # (browser frontend), so JavaScript never has to store it.
    auth_cookie_name: str = "access_token"
    # None = secure cookies only in production. SameSite=none is needed when frontend and API
    # are on different sites in production (it requires Secure).
    cookie_secure: bool | None = None
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # CORS: comma-separated list of exact frontend origins
    cors_origins: Annotated[list[str], NoDecode] = []

    # ML artifacts
    model_dir: Path = BACKEND_ROOT / "models_store"
    # Risk policy on the predicted final-exam percentage (see app/ml/risk.py):
    # high < risk_high_below <= medium < risk_medium_below <= low
    risk_high_below: float = Field(default=50, gt=0, lt=100)
    risk_medium_below: float = Field(default=60, gt=0, le=100)

    @model_validator(mode="after")
    def risk_thresholds_ordered(self) -> "Settings":
        if self.risk_high_below >= self.risk_medium_below:
            raise ValueError("RISK_HIGH_BELOW must be lower than RISK_MEDIUM_BELOW")
        return self

    @model_validator(mode="after")
    def production_is_locked_down(self) -> "Settings":
        """Refuse to start in production with settings that are only acceptable locally."""
        if self.environment != "production":
            return self
        problems = []
        if not self.cors_origins or "*" in self.cors_origins:
            problems.append("CORS_ORIGINS must list the exact frontend origin(s)")
        if any(not origin.startswith("https://") for origin in self.cors_origins):
            problems.append("CORS_ORIGINS must use https:// in production")
        if not self.database_url.get_secret_value().startswith("mysql"):
            problems.append("DATABASE_URL must be a MySQL URL in production")
        if not self.db_ssl_ca:
            problems.append("DB_SSL_CA must be set so the database connection uses verified TLS")
        if problems:
            raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self

    @property
    def cookies_secure(self) -> bool:
        if self.cookie_samesite == "none":
            return True  # browsers reject SameSite=None without Secure
        return self.environment == "production" if self.cookie_secure is None else self.cookie_secure

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return one cached Settings instance (overridable in tests)."""
    return Settings()
