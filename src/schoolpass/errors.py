from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from jwt import InvalidTokenError
from starlette.responses import Response


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        http_status: int,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication required", code: str = "unauthenticated") -> None:
        super().__init__(code, message, status.HTTP_401_UNAUTHORIZED)


class AuthorizationError(AppError):
    def __init__(self, message: str = "Not permitted", code: str = "forbidden") -> None:
        super().__init__(code, message, status.HTTP_403_FORBIDDEN)


class ValidationFailed(AppError):
    def __init__(self, message: str, code: str = "validation_error") -> None:
        super().__init__(code, message, status.HTTP_422_UNPROCESSABLE_ENTITY)


class NotFoundError(AppError):
    def __init__(self, message: str = "Not found", *, code: str = "not_found") -> None:
        super().__init__(code, message, status.HTTP_404_NOT_FOUND)


class ConflictError(AppError):
    def __init__(self, message: str, code: str = "conflict") -> None:
        super().__init__(code, message, status.HTTP_409_CONFLICT)


class RateLimitError(AppError):
    def __init__(self, message: str = "Rate limit exceeded", code: str = "rate_limited") -> None:
        super().__init__(code, message, status.HTTP_429_TOO_MANY_REQUESTS)


class TenantIsolationError(AppError):
    def __init__(self, message: str = "Tenant isolation failed", code: str = "tenant_isolation") -> None:
        super().__init__(code, message, status.HTTP_403_FORBIDDEN)


class DependencyError(AppError):
    def __init__(self, message: str = "Dependency unavailable", code: str = "dependency_failure") -> None:
        super().__init__(code, message, status.HTTP_503_SERVICE_UNAVAILABLE)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", request.headers.get("x-request-id", ""))


def error_body(code: str, message: str, request_id: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content=error_body(exc.code, exc.message, _request_id(request)),
    )


async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = "http_error"
    if exc.status_code == 401:
        code = "unauthenticated"
    elif exc.status_code == 403:
        code = "forbidden"
    elif exc.status_code == 404:
        code = "not_found"
    elif exc.status_code == 409:
        code = "conflict"
    elif exc.status_code == 429:
        code = "rate_limited"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(code, str(exc.detail), _request_id(request)),
    )


async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_body("validation_error", "Request validation failed", _request_id(request)),
    )


async def jwt_error_handler(request: Request, exc: InvalidTokenError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=error_body("unauthenticated", "Invalid token", _request_id(request)),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> Response:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body("internal_error", "An internal error occurred", _request_id(request)),
    )
