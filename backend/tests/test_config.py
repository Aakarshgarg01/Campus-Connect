"""Phase 10: production configuration is refused unless it is locked down."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings

SAFE = {
    "environment": "production",
    "database_url": "mysql+pymysql://u:p@db.example.com:3306/student_predictor",
    "jwt_secret": "x" * 40,
    "cors_origins": "https://app.example.com",
    "db_ssl_ca": "/etc/ssl/certs/ca-certificates.crt",
    "cookie_samesite": "none",
}


def build(**overrides):
    return Settings(_env_file=None, **{**SAFE, **overrides})


def test_locked_down_production_settings_load():
    settings = build()
    assert settings.cors_origins == ["https://app.example.com"]
    assert settings.cookies_secure is True


@pytest.mark.parametrize(("override", "message"), [
    ({"cors_origins": ""}, "exact frontend origin"),
    ({"cors_origins": "*"}, "exact frontend origin"),
    ({"cors_origins": "http://app.example.com"}, "https://"),
    ({"database_url": "sqlite://"}, "MySQL URL"),
    ({"db_ssl_ca": ""}, "verified TLS"),
])
def test_unsafe_production_settings_are_rejected(override, message):
    with pytest.raises(ValidationError, match=message):
        build(**override)


def test_development_allows_local_settings():
    settings = build(environment="development", cors_origins="http://localhost:8080", db_ssl_ca="",
                     cookie_samesite="lax")
    assert settings.cookies_secure is False
