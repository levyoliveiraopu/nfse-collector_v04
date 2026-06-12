"""Utilitarios de logging estruturado e redacao de dados sensiveis."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Mapping
from typing import Any

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
    """Redige tokens, senhas/ciphertexts e URLs presigned em texto livre."""
    value = _PRESIGNED_URL_RE.sub(REDACTED_URL, value)
    value = _BEARER_RE.sub(f"Bearer {REDACTED}", value)
    value = _JSON_VALUE_RE.sub(lambda match: f'{match.group(1)}"{REDACTED}"', value)
    return _KEY_VALUE_RE.sub(lambda match: f"{match.group(1)}={REDACTED}", value)


def redact_value(value: Any, *, key: str | None = None) -> Any:
    """Redige valores sensiveis mantendo tipos simples quando seguro."""
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
    """Filtro que redige segredos antes do formatter JSON/humano."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = ()
        for key, value in list(record.__dict__.items()):
            if key in _RESERVED_LOG_RECORD_ATTRS:
                continue
            record.__dict__[key] = redact_value(value, key=key)
        return True


def build_json_handler() -> logging.Handler:
    """Cria handler stdout JSON Lines com filtro de redacao instalado."""
    from pythonjsonlogger import jsonlogger  # type: ignore[import-untyped]

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(SensitiveDataFilter())
    handler.setFormatter(
        jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        )
    )
    return handler


def configure_json_logging(level: int | str = logging.INFO) -> None:
    """Configura logging raiz JSON + filtro de redacao, com fallback humano."""
    numeric_level = getattr(logging, str(level).upper(), level) if isinstance(level, str) else level
    try:
        handler = build_json_handler()
        logging.basicConfig(level=numeric_level, handlers=[handler], force=True)
    except ImportError:
        handler = logging.StreamHandler(sys.stdout)
        handler.addFilter(SensitiveDataFilter())
        logging.basicConfig(
            level=numeric_level,
            handlers=[handler],
            format="%(asctime)s %(levelname)s %(name)s - %(message)s",
            force=True,
        )
