"""Cliente S3 do `worker-core` (CORE-05).

Upload de XMLs de NFS-e e exports (Excel/ZIP) para o bucket S3-compativel
do ADR-003 (Backblaze B2 como primario). Esta entrega cobre apenas o
cliente reusavel; a integracao com `batch_processor` / orquestrador e
responsabilidade de API-11 / CORE-04.

Layout de chaves (alinhado ao ADR-003 e `infra/s3-bucket.md` — o B2
so aceita prefix literal em lifecycle, por isso `exports` vai num
prefix irmao em vez de `tenants/{tid}/exports/`):

    {S3_EXECUTIONS_PREFIX}{tenant_id}/executions/{execution_id}/{nsu}.xml
    {S3_EXPORTS_PREFIX}{tenant_id}/{file_id}.{ext}

A classe `S3StorageClient` e fina e stateless (o cliente boto3 e
cacheado via `functools.lru_cache` na instancia). Nao faz cifra — o
fluxo de PFX cifrado fica no `apps/api/api/storage.py`, porque a KEK
mora na API.

Retry:

- Camada botocore: `retries={"max_attempts": 3, "mode": "standard"}`
  cobre erros de rede baixos.
- Camada tenacity (este modulo): backoff exponencial explicito em cima
  de erros transientes S3 (`SlowDown`, `ServiceUnavailable`,
  `InternalError`, `RequestTimeout`, `ThrottlingException`) — o ticket
  CORE-05 pede "retry com backoff em falha transitoria" e queremos
  comportamento auditavel sem depender exclusivamente do default do
  botocore. Erros nao-transientes (`AccessDenied`, `NoSuchBucket`,
  `InvalidAccessKeyId`, ...) propagam imediatamente como
  `StorageError`.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional, Union
from uuid import UUID

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("worker_core.storage")


# Codigos de erro considerados transientes — fazem sentido re-tentar.
# Mantemos um conjunto pequeno e explicito para nao mascarar bugs
# (ex.: `AccessDenied` jamais deve virar retry-loop).
_TRANSIENT_ERROR_CODES = frozenset(
    {
        "SlowDown",
        "ServiceUnavailable",
        "InternalError",
        "RequestTimeout",
        "RequestTimeoutException",
        "ThrottlingException",
        "Throttling",
        "503",
        "500",
    }
)


# Content-Type por extensao de export. Fallback `application/octet-stream`.
_EXPORT_CONTENT_TYPES = {
    "xlsx": (
        "application/"
        "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
    "xls": "application/vnd.ms-excel",
    "csv": "text/csv; charset=utf-8",
    "zip": "application/zip",
    "pdf": "application/pdf",
    "json": "application/json; charset=utf-8",
}


class StorageError(RuntimeError):
    """Erro generico de storage. Mascara detalhes do provedor."""


def _is_transient(exc: BaseException) -> bool:
    """True se `exc` for um erro S3 que vale a pena re-tentar."""
    if isinstance(exc, EndpointConnectionError):
        return True
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        return code in _TRANSIENT_ERROR_CODES
    return False


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class S3Settings:
    """Configuracao do cliente S3.

    Espelha as vars `S3_*` do `config/.env.example` (INFRA-06). O worker
    e um pacote independente — nao depende de `apps/api/config`.
    """

    bucket: str
    endpoint: Optional[str] = None
    region: Optional[str] = None
    key_id: Optional[str] = None
    application_key: Optional[str] = None
    force_path_style: bool = True
    executions_prefix: str = "tenants/"
    exports_prefix: str = "tenants-exports/"

    @classmethod
    def from_env(cls, env: Optional[dict[str, str]] = None) -> "S3Settings":
        """Constroi a partir de um dict de envs (default: `os.environ`).

        `S3_BUCKET` e obrigatorio; os outros tem default razoavel.
        """
        src = env if env is not None else os.environ
        bucket = (src.get("S3_BUCKET") or "").strip()
        if not bucket:
            raise StorageError(
                "S3_BUCKET nao configurado. Defina as envs S3_* em config/.env."
            )

        def _clean(key: str, default: Optional[str] = None) -> Optional[str]:
            value = src.get(key)
            if value is None:
                return default
            value = value.strip()
            return value or default

        force_raw = (src.get("S3_FORCE_PATH_STYLE") or "true").strip().lower()
        return cls(
            bucket=bucket,
            endpoint=_clean("S3_ENDPOINT"),
            region=_clean("S3_REGION"),
            key_id=_clean("S3_KEY_ID"),
            application_key=_clean("S3_APPLICATION_KEY"),
            force_path_style=force_raw in {"1", "true", "yes", "on"},
            executions_prefix=_clean("S3_EXECUTIONS_PREFIX", "tenants/")
            or "tenants/",
            exports_prefix=_clean("S3_EXPORTS_PREFIX", "tenants-exports/")
            or "tenants-exports/",
        )


# ---------------------------------------------------------------------------
# Object-key builders
# ---------------------------------------------------------------------------


def _normalize_prefix(prefix: str) -> str:
    if not prefix:
        return ""
    return prefix if prefix.endswith("/") else prefix + "/"


def _coerce_uuid(value: Union[str, UUID], field: str) -> UUID:
    try:
        if isinstance(value, UUID):
            return value
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"{field} nao e um UUID valido: {value!r}") from exc


def _normalize_ext(ext: str) -> str:
    if not isinstance(ext, str) or not ext.strip():
        raise ValueError("ext vazio ou invalido")
    cleaned = ext.strip().lower().lstrip(".")
    if not cleaned or not all(c.isalnum() for c in cleaned):
        raise ValueError(f"ext invalido: {ext!r}")
    return cleaned


def xml_object_key(
    tenant_id: Union[str, UUID],
    execution_id: Union[str, UUID],
    nsu: int,
    *,
    prefix: str = "tenants/",
) -> str:
    """Compoe a chave canonica de um XML coletado.

    Formato: `{prefix}{tenant_id}/executions/{execution_id}/{nsu}.xml`.
    """
    if not isinstance(nsu, int) or isinstance(nsu, bool) or nsu < 0:
        raise ValueError(f"nsu deve ser int >= 0, recebido {nsu!r}")
    tid = _coerce_uuid(tenant_id, "tenant_id")
    eid = _coerce_uuid(execution_id, "execution_id")
    return (
        f"{_normalize_prefix(prefix)}{tid}/executions/{eid}/{nsu}.xml"
    )


def export_object_key(
    tenant_id: Union[str, UUID],
    file_id: Union[str, UUID],
    ext: str,
    *,
    prefix: str = "tenants-exports/",
) -> str:
    """Compoe a chave canonica de um export (Excel/ZIP/...).

    Formato: `{prefix}{tenant_id}/{file_id}.{ext}`.
    """
    tid = _coerce_uuid(tenant_id, "tenant_id")
    fid = _coerce_uuid(file_id, "file_id")
    clean_ext = _normalize_ext(ext)
    return f"{_normalize_prefix(prefix)}{tid}/{fid}.{clean_ext}"


# ---------------------------------------------------------------------------
# Upload result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UploadResult:
    """Resultado de um upload bem-sucedido."""

    object_key: str
    sha256: str  # hex lowercase, 64 chars
    size: int


# ---------------------------------------------------------------------------
# Cliente S3
# ---------------------------------------------------------------------------


class S3StorageClient:
    """Cliente fino para upload de XML e exports no bucket S3-compat.

    Uso tipico:

    >>> client = S3StorageClient()                         # le envs
    >>> res = client.upload_xml(tenant_id, exec_id, 42, b"<xml/>")
    >>> res.object_key
    'tenants/<tid>/executions/<eid>/42.xml'
    >>> res.sha256
    '<hex>'
    """

    def __init__(self, settings: Optional[S3Settings] = None) -> None:
        self._settings = settings or S3Settings.from_env()
        # Cache do cliente boto3 por instancia — e seguro reusar entre
        # threads e cheap para manter durante o lifetime do worker.
        self._client_cached = lru_cache(maxsize=1)(self._build_client)

    # ---- infra ------------------------------------------------------------

    @property
    def settings(self) -> S3Settings:
        return self._settings

    def _build_client(self):
        s = self._settings
        kwargs = {
            "service_name": "s3",
            "region_name": s.region or "us-east-1",
            "config": BotoConfig(
                s3={
                    "addressing_style": (
                        "path" if s.force_path_style else "auto"
                    )
                },
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        }
        if s.endpoint:
            kwargs["endpoint_url"] = s.endpoint
        if s.key_id and s.application_key:
            kwargs["aws_access_key_id"] = s.key_id
            kwargs["aws_secret_access_key"] = s.application_key
        return boto3.client(**kwargs)

    def _client(self):
        return self._client_cached()

    # ---- upload primitives -----------------------------------------------

    def _put(
        self,
        key: str,
        body: bytes,
        content_type: str,
        extra_metadata: Optional[dict[str, str]] = None,
    ) -> UploadResult:
        if not isinstance(body, (bytes, bytearray)):
            raise TypeError(
                f"body deve ser bytes, recebido {type(body).__name__}"
            )
        payload = bytes(body)
        sha = hashlib.sha256(payload).hexdigest()
        metadata = {"sha256": sha}
        if extra_metadata:
            metadata.update(extra_metadata)

        bucket = self._settings.bucket

        @retry(
            reraise=True,
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8.0),
            retry=retry_if_exception(_is_transient),
            before_sleep=lambda rs: logger.warning(
                "storage.put.retry",
                extra={
                    "key": key,
                    "attempt": rs.attempt_number,
                },
            ),
        )
        def _do_put() -> None:
            client = self._client()
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=payload,
                ContentType=content_type,
                Metadata=metadata,
            )

        try:
            _do_put()
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            logger.error(
                "storage.put.failed",
                extra={
                    "key": key,
                    "error_code": code,
                    "transient": _is_transient(exc),
                },
            )
            raise StorageError(
                f"falha ao gravar objeto no storage (code={code!r})"
            ) from exc
        except EndpointConnectionError as exc:
            logger.error(
                "storage.put.failed",
                extra={
                    "key": key,
                    "error_code": "EndpointConnectionError",
                    "transient": True,
                },
            )
            raise StorageError(
                "falha ao gravar objeto no storage apos retries"
            ) from exc
        except BotoCoreError as exc:
            logger.error(
                "storage.put.failed",
                extra={"key": key, "error_code": type(exc).__name__},
            )
            raise StorageError("falha ao gravar objeto no storage") from exc

        logger.info(
            "storage.put.ok",
            extra={"key": key, "size": len(payload), "sha256": sha},
        )
        return UploadResult(object_key=key, sha256=sha, size=len(payload))

    # ---- API publica ------------------------------------------------------

    def upload_xml(
        self,
        tenant_id: Union[str, UUID],
        execution_id: Union[str, UUID],
        nsu: int,
        xml_bytes: bytes,
    ) -> UploadResult:
        """Sobe um XML coletado. Devolve `object_key` + `sha256` + `size`."""
        key = xml_object_key(
            tenant_id,
            execution_id,
            nsu,
            prefix=self._settings.executions_prefix,
        )
        return self._put(
            key,
            xml_bytes,
            content_type="application/xml",
            extra_metadata={"nsu": str(nsu)},
        )

    def upload_export(
        self,
        tenant_id: Union[str, UUID],
        file_id: Union[str, UUID],
        path_or_bytes: Union[bytes, str, os.PathLike],
        ext: str,
    ) -> UploadResult:
        """Sobe um export (Excel/ZIP/...). Aceita bytes ou caminho local."""
        if isinstance(path_or_bytes, (bytes, bytearray)):
            body = bytes(path_or_bytes)
        else:
            path = Path(path_or_bytes)
            try:
                body = path.read_bytes()
            except OSError as exc:
                raise StorageError(
                    f"nao foi possivel ler arquivo para upload: {path}"
                ) from exc

        clean_ext = _normalize_ext(ext)
        content_type = _EXPORT_CONTENT_TYPES.get(
            clean_ext, "application/octet-stream"
        )
        key = export_object_key(
            tenant_id,
            file_id,
            clean_ext,
            prefix=self._settings.exports_prefix,
        )
        return self._put(
            key,
            body,
            content_type=content_type,
            extra_metadata={"ext": clean_ext},
        )


