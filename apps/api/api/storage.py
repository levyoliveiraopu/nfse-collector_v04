"""Cliente S3 (Backblaze B2 / qualquer S3-compat) para a API (API-06).

Escopo minimo desta primeira entrega: armazenar/remover blobs cifrados
de credenciais PFX. Operacoes de ciclo de vida (lifecycle, versioning,
quota) sao geridas no console B2 — ver `infra/s3-bucket.md`.

Layout de chaves para credenciais (ADR-003 + INFRA-06):

    {S3_CREDENTIALS_PREFIX}{tenant_id}/{credential_id}.pfx.enc

`S3_CREDENTIALS_PREFIX` (default `tenants-credentials/`) e DELIBERADAMENTE
distinto de `S3_EXECUTIONS_PREFIX` (`tenants/`, lifecycle 90d) porque
credenciais sao vivas — apaga-las por TTL quebraria o coletor sem aviso.
O owner deve garantir que NAO existe lifecycle rule no console do B2
para esse prefix; o runbook em `infra/s3-bucket.md` documenta isso.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional
from uuid import UUID

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from .config import get_settings

logger = logging.getLogger("api.storage")


class StorageError(RuntimeError):
    """Erro generico de storage. Mascara detalhes do provedor."""


@lru_cache(maxsize=1)
def _get_s3_client():
    """Cria o cliente boto3 S3 lazy. Cacheado por processo."""
    settings = get_settings()
    if not settings.s3_bucket:
        raise StorageError(
            "S3_BUCKET nao configurado. Defina as envs S3_* em config/.env."
        )

    kwargs = {
        "service_name": "s3",
        "region_name": settings.s3_region or "us-east-1",
        "config": BotoConfig(
            s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"},
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    }
    if settings.s3_endpoint:
        kwargs["endpoint_url"] = settings.s3_endpoint
    if settings.s3_key_id and settings.s3_application_key:
        kwargs["aws_access_key_id"] = settings.s3_key_id
        kwargs["aws_secret_access_key"] = settings.s3_application_key

    return boto3.client(**kwargs)


def reset_client_for_tests() -> None:
    """Limpa o cache do cliente boto3. Apenas para uso em testes."""
    _get_s3_client.cache_clear()


def credential_object_key(tenant_id: UUID | str, credential_id: UUID | str) -> str:
    """Compoe a chave canonica do blob cifrado de uma credencial PFX."""
    settings = get_settings()
    prefix = settings.s3_credentials_prefix
    if not prefix.endswith("/"):
        prefix = prefix + "/"
    tid = str(UUID(str(tenant_id)))
    cid = str(UUID(str(credential_id)))
    return f"{prefix}{tid}/{cid}.pfx.enc"


def put_credential_blob(
    tenant_id: UUID | str,
    credential_id: UUID | str,
    ciphertext: bytes,
) -> str:
    """PUT do ciphertext no bucket. Devolve o `object_key` gravado."""
    settings = get_settings()
    key = credential_object_key(tenant_id, credential_id)
    client = _get_s3_client()
    try:
        client.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=ciphertext,
            ContentType="application/octet-stream",
            # Marcamos a versao do envelope no metadado para auditoria
            # (nao e usado para decifrar — o version_tag esta nos bytes).
            Metadata={"envelope-version": "1"},
        )
    except ClientError as exc:
        logger.error(
            "storage.put.failed",
            extra={"key": key, "error_code": exc.response.get("Error", {}).get("Code")},
        )
        raise StorageError("falha ao gravar credencial no storage") from exc
    return key


def delete_credential_blob(object_key: str) -> bool:
    """DELETE do blob. Devolve True se removeu, False se ja nao existia.

    Em S3, `delete_object` e idempotente (200 mesmo se a chave nao existe).
    Aqui distinguimos via `head_object` previo apenas quando o caller
    quer logar com precisao — best-effort.
    """
    settings = get_settings()
    client = _get_s3_client()
    existed = True
    try:
        client.head_object(Bucket=settings.s3_bucket, Key=object_key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            existed = False
        # Para outros erros, deixa propagar via DELETE abaixo.

    try:
        client.delete_object(Bucket=settings.s3_bucket, Key=object_key)
    except ClientError as exc:
        logger.warning(
            "storage.delete.failed",
            extra={"key": object_key, "error_code": exc.response.get("Error", {}).get("Code")},
        )
        raise StorageError("falha ao remover credencial do storage") from exc
    return existed


def get_credential_blob(object_key: str) -> Optional[bytes]:
    """GET do blob cifrado. Retorna `None` se a chave nao existe."""
    settings = get_settings()
    client = _get_s3_client()
    try:
        resp = client.get_object(Bucket=settings.s3_bucket, Key=object_key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise StorageError("falha ao ler credencial do storage") from exc
    return resp["Body"].read()
