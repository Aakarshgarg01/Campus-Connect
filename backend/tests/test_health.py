"""Phase 3 tests: /health, consistent error format, request IDs and CORS."""

from __future__ import annotations

from tests.conftest import FRONTEND, UNREACHABLE_MYSQL


def test_health_ok_when_database_and_models_available(make_client, model_dir):
    response = make_client(model_dir=model_dir).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == {"connected": True}
    assert body["models"]["stage1"]["loaded"] is True
    assert body["models"]["stage1"]["model_version"] == "stage1-test"
    # The tiny test models ship no SHAP background, so health says so (predictions still work).
    assert body["models"]["stage1"]["explainer_ready"] is False
    assert body["models"]["stage1"]["explainer_error"] == "SHAP background file is missing"
    assert body["models"]["stage2"]["loaded"] is True


def test_health_503_when_models_missing(make_client):
    response = make_client().get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"]["connected"] is True
    assert body["models"]["stage1"] == {"loaded": False, "reason": "model file or metadata.json is missing"}


def test_health_503_when_model_file_corrupt(make_client, model_dir):
    (model_dir / "stage2" / "model.joblib").write_bytes(b"not a pickle")
    body = make_client(model_dir=model_dir).get("/health").json()
    assert body["models"]["stage1"]["loaded"] is True
    assert body["models"]["stage2"]["loaded"] is False
    assert body["models"]["stage2"]["reason"] == "model file does not match metadata.json (sha256 mismatch)"


def test_health_503_when_database_unreachable(make_client, model_dir):
    response = make_client(database_url=UNREACHABLE_MYSQL, model_dir=model_dir).get("/health")
    assert response.status_code == 503
    database = response.json()["database"]
    assert database["connected"] is False
    assert database["error"] == "OperationalError"
    assert "nobody" not in response.text  # credentials never leak


def test_unknown_route_uses_error_format(make_client):
    response = make_client().get("/does-not-exist", headers={"X-Request-ID": "abc123"})
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Not Found", "details": None},
        "request_id": "abc123",
    }
    assert response.headers["X-Request-ID"] == "abc123"


def test_validation_and_unhandled_errors_use_error_format(make_client):
    client = make_client()

    @client.app.get("/_test/number/{value}")
    def number(value: int) -> dict[str, int]:
        return {"value": value}

    @client.app.get("/_test/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    invalid = client.get("/_test/number/abc")
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"
    assert invalid.json()["error"]["details"][0]["field"] == "path.value"

    crashed = client.get("/_test/boom")
    assert crashed.status_code == 500
    assert crashed.json()["error"] == {
        "code": "internal_error",
        "message": "An unexpected error occurred.",
        "details": None,
    }
    assert "secret internal detail" not in crashed.text


def test_cors_allows_configured_origin_only(make_client):
    client = make_client()
    preflight = {"Access-Control-Request-Method": "GET"}
    allowed = client.options("/health", headers={"Origin": FRONTEND, **preflight})
    assert allowed.headers.get("access-control-allow-origin") == FRONTEND
    blocked = client.options("/health", headers={"Origin": "https://evil.example", **preflight})
    assert "access-control-allow-origin" not in blocked.headers
