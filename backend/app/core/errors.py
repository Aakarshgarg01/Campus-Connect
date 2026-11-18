"""One error format for every failure response, plus per-request IDs and access logging.

Every error body looks like:
    {"error": {"code": "not_found", "message": "...", "details": ...}, "request_id": "..."}
Unhandled exceptions are logged with their stack trace but never exposed to the client.
"""

from __future__ import annotations

import logging
import time
import uuid
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.request")

REQUEST_ID_HEADER = "X-Request-ID"


class AppError(Exception):
    """An expected failure with a stable machine-readable code, e.g. model_unavailable."""

    def __init__(self, status_code: int, code: str, message: str, details: object = None) -> None:
        super().__init__(message)
        self.status_code, self.code, self.message, self.details = status_code, code, message, details


# Fixed codes for statuses whose HTTP reason phrase differs between Python versions.
_FIXED_CODES = {422: "unprocessable_entity"}


def _code_for(status_code: int) -> str:
    if status_code in _FIXED_CODES:
        return _FIXED_CODES[status_code]
    try:
        return HTTPStatus(status_code).phrase.lower().replace(" ", "_").replace("-", "_")
    except ValueError:
        return "error"


def error_response(
    request: Request,
    status_code: int,
    message: str,
    *,
    code: str | None = None,
    details: object = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = {
        "error": {"code": code or _code_for(status_code), "message": message, "details": details},
        "request_id": getattr(request.state, "request_id", None),
    }
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body), headers=headers)


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
    details = None if isinstance(exc.detail, str) else exc.detail
    return error_response(
        request, exc.status_code, message, details=details, headers=getattr(exc, "headers", None)
    )


async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"field": ".".join(str(part) for part in err["loc"]), "message": err["msg"], "type": err["type"]}
        for err in exc.errors()
    ]
    return error_response(
        request, 422, "Request validation failed.", code="validation_error", details=details
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", extra={"request_id": getattr(request.state, "request_id", None)})
    return error_response(request, 500, "An unexpected error occurred.", code="internal_error")


async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return error_response(request, exc.status_code, exc.message, code=exc.code, details=exc.details)


def install_error_handling(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        # Accept a client-supplied ID only if it is short and safe to log.
        request_id = incoming if 0 < len(incoming) <= 64 and incoming.isascii() and incoming.isprintable() else uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        finally:
            logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
