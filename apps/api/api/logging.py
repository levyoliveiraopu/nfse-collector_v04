"""Logging estruturado em JSON para a API.

Escreve no stdout no formato JSON Lines, compativel com coletores
(Loki/CloudWatch/Datadog). Inclui timestamp, nivel, logger, mensagem
e quaisquer extras passados via `logger.info(..., extra={...})`.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Mapping
from typing import Any

from pythonjsonlogger import jsonlogger

REDACTED = "[REDACTED]"
REDACTED_URL = "[REDACTED_URL]"

_SENSITIVE_KEYS = (
    "authorization",
    "access_token",
    "refresh_token",
    "id_token",
    "token",
    "jwt",
    "secret",
    "password",
    "senha",
    "pfx",
    "ciphertext",
    "private_key",
    "application_key",
    "presigned_url",
)
_KEY_VALUE_RE = re.compile(
    r"(?i)\b(access_token|refresh_token|id_token|token|jwt|secret|password|senha|pfx_password|ciphertext)"
    r"\s*[:=]\s*([^\s,;&]+)"
)
_JSON_VALUE_RE = re.compile(
    r'(?i)("(?:access_token|refresh_token|id_token|token|jwt|secret|password|senha|pfx_password|ciphertext)"\s*:\s*)"[^"]*"'
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_PRESIGNED_URL_RE = re.compile(
    r"https?://[^\s\"']+\?(?=[^\s\"']*(?:X-Amz-Signature|X-Amz-Credential|AWSAccessKeyId|Signature=|Expires=))[^\s\"']+"
)
_RESERVED_LOG_RECORD_ATTRS = set(logging.makeLogRecord({}).__dict__)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _SENSITIVE_KEYS)


def redact_text(value: str) -> str:
    value = _PRESIGNED_URL_RE.sub(REDACTED_URL, value)
    value = _BEARER_RE.sub(f"Bearer {REDACTED}", value)
    value = _JSON_VALUE_RE.sub(lambda match: f'{match.group(1)}"{REDACTED}"', value)
    return _KEY_VALUE_RE.sub(lambda match: f"{match.group(1)}={REDACTED}", value)


def redact_value(value: Any, *, key: str | None = None) -> Any:
    if key and _is_sensitive_key(key):
        return REDACTED_URL if "url" in key.lower() else REDACTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, bytes):
        return REDACTED
    if isinstance(value, Mapping):
        return {str(k): redact_value(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, tuple):
        return tuple(redact_value(v) for v in value)
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    if isinstance(value, set):
        return {redact_value(v) for v in value}
    return value


class SensitiveDataFilter(logging.Filter):
    """Redige segredos antes de serializar logs JSON."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = ()
        for key, value in list(record.__dict__.items()):
            if key in _RESERVED_LOG_RECORD_ATTRS:
                continue
            record.__dict__[key] = redact_value(value, key=key)
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configura o root logger para emitir JSON no stdout.

    Idempotente: remove handlers previos antes de instalar o novo,
    evitando logs duplicados em reload do uvicorn.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(SensitiveDataFilter())
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
