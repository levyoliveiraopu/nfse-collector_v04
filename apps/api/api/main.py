"""Entry point da API FastAPI (API-01).

Expoe endpoints basicos de observabilidade:
- GET /health  -> liveness simples.
- GET /version -> versao do pacote + commit (quando disponivel).
"""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI

from .config import Settings, get_settings
from .logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
    )

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

    return app


app = create_app()
