"""Consistent error model per docs/ERROR_HANDLING.md.

Every error → {"error": {"code", "message", "details", "request_id"}}.
Never leak stack traces / SQL / secrets to clients.
"""
from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import request_id_ctx

log = logging.getLogger("svault.errors")


class ErrorCode(StrEnum):
    validation_error = "validation_error"
    unauthorized = "unauthorized"
    forbidden = "forbidden"
    not_found = "not_found"
    conflict = "conflict"
    duplicate_document = "duplicate_document"
    rate_limited = "rate_limited"
    entitlement_required = "entitlement_required"
    payment_required = "payment_required"
    upstream_error = "upstream_error"
    internal_error = "internal_error"


_STATUS = {
    ErrorCode.validation_error: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ErrorCode.unauthorized: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.forbidden: status.HTTP_403_FORBIDDEN,
    ErrorCode.not_found: status.HTTP_404_NOT_FOUND,
    ErrorCode.conflict: status.HTTP_409_CONFLICT,
    ErrorCode.duplicate_document: status.HTTP_409_CONFLICT,
    ErrorCode.rate_limited: status.HTTP_429_TOO_MANY_REQUESTS,
    ErrorCode.entitlement_required: status.HTTP_403_FORBIDDEN,
    ErrorCode.payment_required: status.HTTP_402_PAYMENT_REQUIRED,
    ErrorCode.upstream_error: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.internal_error: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


class AppError(Exception):
    """Raise this anywhere to return a clean, coded error."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Any | None = None,
        http_status: int | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details
        self.http_status = http_status or _STATUS[code]
        super().__init__(message)


def not_found(message: str = "Not found") -> AppError:
    # NOTE: for cross-tenant / non-owned objects, return not_found (NOT forbidden)
    # so record existence is never revealed. See ERROR_HANDLING.md.
    return AppError(ErrorCode.not_found, message)


def _envelope(code: str, message: str, details: Any | None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id_ctx.get(),
        }
    }


def _cors_headers(request: Request) -> dict[str, str]:
    """CORS headers for an error response that bypasses CORSMiddleware.

    The catch-all Exception (500) handler is invoked by Starlette's outermost
    ServerErrorMiddleware — *outside* CORSMiddleware — so its responses carry no
    Access-Control-Allow-Origin header and the browser masks the real 500 as a
    misleading "blocked by CORS policy" error. We re-derive the same headers
    CORSMiddleware would have added: echo the request Origin when it is allowed.
    """
    from app.core.config import settings  # local import avoids a config import cycle

    origin = request.headers.get("origin")
    if not origin:
        return {}
    allowed = settings.cors_origins_list
    permit_all = not allowed and not settings.is_prod
    if permit_all or origin in allowed:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=_envelope(exc.code.value, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                ErrorCode.validation_error.value, "Validation failed", exc.errors()
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Log the full trace server-side; return a generic 500 to the client.
        # This handler runs in ServerErrorMiddleware (outside CORSMiddleware), so we
        # must attach CORS headers ourselves — otherwise the browser reports a 500 as
        # a misleading "blocked by CORS policy" error and the real envelope is hidden.
        log.exception("unhandled_error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(
                ErrorCode.internal_error.value, "Something went wrong", None
            ),
            headers=_cors_headers(request),
        )
