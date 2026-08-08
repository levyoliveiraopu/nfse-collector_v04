"""Entry point da API FastAPI.

Expoe endpoints basicos de observabilidade (API-01) e o router de
autenticacao (API-02) em `/auth/*`.
"""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .auth.routes import limiter as auth_limiter
from .auth.routes import router as auth_router
from .companies.credentials import router as credentials_router
from .db import get_admin_session
from .queue import QueueError, ping_redis
from .companies.routes import router as companies_router
from .config import Settings, get_settings
from .schedules.routes import router as schedules_router
from .files.routes import router as files_router
from .help.routes import router as help_router
from .executions.routes import router as executions_router
from .exports.routes import router as exports_router
from .logging import configure_logging
from .occurrences.routes import router as occurrences_router
from .onboarding.routes import router as onboarding_router
from .reprocess.routes import router as reprocess_router


def _rate_limit_handler(request, exc: RateLimitExceeded):  # noqa: ARG001
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=429,
        content={"detail": "muitas tentativas; tente novamente em instantes"},
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
    )

    # Rate limit global (compartilha o limiter definido no modulo auth).
    app.state.limiter = auth_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)

    logger = logging.getLogger("api")
    logger.info(
        "api.startup",
        extra={
            "environment": settings.environment,
            "version": settings.version,
            "git_commit": settings.git_commit,
        },
    )

    @app.get("/health", tags=["observability"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["observability"])
    def ready(settings: Settings = Depends(get_settings)):
        checks: dict[str, bool] = {
            "database": False,
            "redis": False,
            "storage_config": False,
        }
        details: dict[str, str] = {}

        try:
            with get_admin_session() as session:
                session.execute(text("SELECT 1"))
            checks["database"] = True
        except Exception as exc:  # noqa: BLE001
            details["database"] = exc.__class__.__name__

        try:
            ping_redis()
            checks["redis"] = True
        except QueueError as exc:
            details["redis"] = str(exc)
        except Exception as exc:  # noqa: BLE001
            details["redis"] = exc.__class__.__name__

        required_storage = {
            "S3_ENDPOINT": settings.s3_endpoint,
            "S3_BUCKET": settings.s3_bucket,
            "S3_KEY_ID": settings.s3_key_id,
            "S3_APPLICATION_KEY": settings.s3_application_key,
        }
        missing_storage = [name for name, value in required_storage.items() if not value]
        checks["storage_config"] = not missing_storage
        if missing_storage:
            details["storage_config"] = "missing:" + ",".join(missing_storage)

        ok = all(checks.values())
        body = {
            "status": "ok" if ok else "not_ready",
            "checks": checks,
        }
        if details:
            body["details"] = details
        if ok:
            return body
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=body)

    @app.get("/version", tags=["observability"])
    def version(settings: Settings = Depends(get_settings)) -> dict[str, str]:
        return {
            "version": settings.version,
            "commit": settings.git_commit,
        }

    app.include_router(auth_router)
    app.include_router(companies_router)
    app.include_router(credentials_router)
    app.include_router(occurrences_router)
    app.include_router(schedules_router)
    app.include_router(files_router)
    app.include_router(executions_router)
    app.include_router(exports_router)
    app.include_router(onboarding_router)
    app.include_router(reprocess_router)
    app.include_router(help_router)

    return app


app = create_app()
