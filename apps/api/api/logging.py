"""Logging estruturado em JSON para a API.

Escreve no stdout no formato JSON Lines, compativel com coletores
(Loki/CloudWatch/Datadog). Inclui timestamp, nivel, logger, mensagem
e quaisquer extras passados via `logger.info(..., extra={...})`.
"""

from __future__ import annotations

import logging
import sys

from pythonjsonlogger import jsonlogger


def configure_logging(level: str = "INFO") -> None:
    """Configura o root logger para emitir JSON no stdout.

    Idempotente: remove handlers previos antes de instalar o novo,
    evitando logs duplicados em reload do uvicorn.
    """
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Alinha loggers do uvicorn/fastapi com o formato JSON.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
