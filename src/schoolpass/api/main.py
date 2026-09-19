from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from jwt import InvalidTokenError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from schoolpass.adapters.blob import LocalBlobStore
from schoolpass.adapters.redis import RedisCache
from schoolpass.adapters.service_bus import AzureServiceBus, LocalRedisBus
from schoolpass.api.routes.admin import router as admin_router
from schoolpass.api.routes.admin_academic import router as admin_academic_router
from schoolpass.api.routes.admin_people import router as admin_people_router
from schoolpass.api.routes.attendance import router as attendance_router
from schoolpass.api.routes.auth import router as auth_router
from schoolpass.api.routes.cards import router as cards_router
from schoolpass.api.routes.health import router as health_router
from schoolpass.api.routes.parent import router as parent_router
from schoolpass.api.routes.parent_notifications import router as parent_notifications_router
from schoolpass.api.routes.people import router as people_router
from schoolpass.api.routes.rfid import router as rfid_router
from schoolpass.api.routes.rfid_ingest import router as rfid_ingest_router
from schoolpass.api.routes.session import router as session_router
from schoolpass.api.routes.teacher import router as teacher_router
from schoolpass.api.routes.teacher_notifications import router as teacher_notifications_router
from schoolpass.api.routes.transport import router as transport_router
from schoolpass.api.routes.transport_gps import router as transport_gps_router
from schoolpass.api.routes.transport_nfc import router as transport_nfc_router
from schoolpass.config import Settings, get_settings
from schoolpass.db.session import create_engine, session_factory
from schoolpass.errors import (
    AppError,
    app_error_handler,
    http_error_handler,
    jwt_error_handler,
    unhandled_error_handler,
    validation_handler,
)
from schoolpass.observability.logging import bind_request_context, configure_logging, get_logger
from schoolpass.observability.metrics import metrics
from schoolpass.observability.tracing import span

log = get_logger("schoolpass.api")


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        bind_request_context(request_id=request_id)
        with span("http.request", request_id=request_id, path=request.url.path):
            response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        metrics.increment("http.requests", path=request.url.path, status=str(response.status_code))
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = create_engine(settings.database_url, null_pool=settings.app_env == "test")
    redis = RedisCache(settings.redis_url)
    blob = LocalBlobStore(settings.blob_local_root)
    bus = (
        AzureServiceBus(settings.azure_service_bus_fully_qualified_namespace)
        if settings.service_bus_mode == "azure"
        else LocalRedisBus(redis)
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        log.info("api_started", env=settings.app_env)
        yield
        await redis.close()
        await engine.dispose()

    app = FastAPI(
        title="SchoolPass API",
        version="0.1.0",
        docs_url="/docs" if settings.app_env in {"local", "test", "staging"} else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory(engine)
    app.state.redis = redis
    app.state.blob = blob
    app.state.bus = bus
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(CorrelationMiddleware)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_handler)
    app.add_exception_handler(InvalidTokenError, jwt_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(session_router)
    app.include_router(people_router)
    app.include_router(cards_router)
    app.include_router(rfid_router)
    app.include_router(rfid_ingest_router)
    app.include_router(attendance_router)
    app.include_router(transport_router)
    app.include_router(transport_nfc_router)
    app.include_router(transport_gps_router)
    app.include_router(parent_router)
    app.include_router(parent_notifications_router)
    app.include_router(teacher_router)
    app.include_router(teacher_notifications_router)
    app.include_router(admin_router)
    app.include_router(admin_academic_router)
    app.include_router(admin_people_router)
    return app


app = create_app()
