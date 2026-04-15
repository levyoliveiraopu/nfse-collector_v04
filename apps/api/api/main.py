"""Entry point da API FastAPI.

Expoe endpoints basicos de observabilidade (API-01) e o router de
autenticacao (API-02) em `/auth/*`.
"""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .auth.routes import limiter as auth_limiter
from .auth.routes import router as auth_router
from .companies.credentials import router as credentials_router
from .companies.routes import router as companies_router
from .config import Settings, get_settings
from .schedules.routes import router as schedules_router
from .logging import configure_logging


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

    @app.get("/version", tags=["observability"])
    def version(settings: Settings = Depends(get_settings)) -> dict[str, str]:
        return {
            "version": settings.version,
            "commit": settings.git_commit,
        }

    app.include_router(auth_router)
    app.include_router(companies_router)
    app.include_router(credentials_router)
    app.include_router(schedules_router)

    return app


app = create_app()
