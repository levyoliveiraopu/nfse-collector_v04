"""Handler RQ `run_execution(execution_id)` — orquestracao ponta-a-ponta (API-13).

Enfileirado pela API em `apps/api/api/queue.py`:

    queue.enqueue("worker_core.jobs.run_execution", str(execution_id), ...)

Fluxo:

    1. Busca `executions` + `companies` + `company_credentials` (RLS via
       `app.current_tenant`).
    2. Le o blob cifrado do S3 (prefixo `S3_CREDENTIALS_PREFIX`) e decifra
       senha + PFX com `worker_core.crypto.decrypt` (envelope AES-256-GCM
       compativel com API-06).
    3. Chama `worker_core.fetch_nfse` com `DbNsuSource` (persiste
       `companies.last_nsu`) + callback que:
        a. INSERE `execution_items` com `ON CONFLICT (tenant_id, chave_nfse)
           DO NOTHING` — **idempotencia**: retry do job nao duplica itens.
        b. Sobe o XML bruto pro S3 (`S3StorageClient`).
        c. Atualiza `execution_items.xml_object_key` com a chave S3.
    4. Marca `executions.status` como `succeeded`/`partial`/`failed`
       de acordo com o resumo da coleta.
    5. Cria `occurrences` para erros categorizados (credencial, portal,
       parse). Codigos alinhados com `docs/architecture/occurrence-codes.md`.

Idempotencia / retry:
- `execution_items` tem unique parcial `(tenant_id, chave_nfse) WHERE
  chave_nfse IS NOT NULL` (DATA-03 / migration 0005). Usamos `ON CONFLICT
  DO NOTHING` no INSERT; uma segunda rodada com a mesma chave nao insere
  linha nova e nao levanta erro.
- Upload S3 e determinista (mesma key, mesmo sha256) — re-subir o mesmo
  XML e seguro.
- Atualizacao de `companies.last_nsu` via `DbNsuSource` ja honra "nunca
  regride".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from worker_core.collector import FetchSummary, NfseItem, fetch_nfse
from worker_core.crypto import CryptoError, decrypt
from worker_core.db import get_admin_session, get_tenant_session
from worker_core.db_nsu import DbNsuSource
from worker_core.storage import S3StorageClient, StorageError

logger = logging.getLogger("worker_core.jobs")


# Codigos de ocorrencia (docs/architecture/occurrence-codes.md).
OCC_CRED_INVALID = "CRED_INVALID"
OCC_CERT_EXPIRED = "CERT_EXPIRED"
OCC_PORTAL_5XX = "PORTAL_5XX"
OCC_PARSE_ERROR = "PARSE_ERROR"
OCC_STORAGE_ERROR = "STORAGE_ERROR"
OCC_UNKNOWN = "UNKNOWN"


class JobError(RuntimeError):
    """Erro de orquestracao do worker. Marca execucao como `failed`."""


@dataclass(frozen=True)
class _ExecutionContext:
    """Snapshot das linhas lidas no inicio do job."""

    execution_id: UUID
    tenant_id: UUID
    company_id: UUID
    cnpj: str
    pfx_object_key: str
    pfx_password_ciphertext: bytes
    credential_id: UUID


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_execution(
    execution_id: str,
    *,
    storage_client: Optional[S3StorageClient] = None,
    read_credential_blob: Optional[Callable[[str], bytes]] = None,
) -> dict:
    """Handler picado pelo RQ worker.

    Args:
        execution_id:         UUID da linha em `executions` (string, como
                              serializado pelo RQ).
        storage_client:       Injecao para testes. Default: `S3StorageClient()`.
        read_credential_blob: Injecao para testes. Default: usa boto3 para
                              ler o blob cifrado do prefixo de credenciais.

    Retorna um dict com o status final e os contadores — expoe para o
    RQ result_ttl. Excecoes nao-capturadas marcam a execucao como `failed`
    e propagam para o RQ (que gravara em failure_ttl).
    """
    eid = _coerce_uuid(execution_id, "execution_id")
    logger.info("jobs.run_execution.start", extra={"execution_id": str(eid)})

    ctx = _load_execution_context(eid)
    if ctx is None:
        # Execucao sumiu entre o enqueue e o pick. Nao temos tenant_id pra
        # marcar como failed — apenas loga e sai (DB e RLS mantem auditoria).
        logger.warning(
            "jobs.run_execution.not_found", extra={"execution_id": str(eid)}
        )
        return {"status": "not_found", "execution_id": str(eid)}

    storage = storage_client if storage_client is not None else S3StorageClient()
    read_blob = read_credential_blob or _default_read_credential_blob

    _mark_running(ctx)

    try:
        pfx_bytes, pfx_password = _decrypt_credential(ctx, read_blob)
    except CryptoError as exc:
        _mark_failed(ctx, error_summary="credential_decrypt_failed")
        _create_occurrence(ctx, code=OCC_CRED_INVALID, severity="error",
                           title="Credencial nao pode ser decifrada", detail=str(exc))
        raise JobError("credential_decrypt_failed") from exc
    except StorageError as exc:
        _mark_failed(ctx, error_summary="credential_blob_missing")
        _create_occurrence(ctx, code=OCC_CRED_INVALID, severity="error",
                           title="Blob de credencial ausente no storage", detail=str(exc))
        raise JobError("credential_blob_missing") from exc

    nsu_source = DbNsuSource(
        tenant_id=ctx.tenant_id,
        company_id=ctx.company_id,
        session_factory=get_tenant_session,
    )

    items_ok = 0
    items_fail = 0
    storage_errors = 0

    def _on_progress(item: NfseItem) -> None:
        nonlocal items_ok, items_fail, storage_errors
        try:
            xml_key: Optional[str] = None
            if item.xml_bytes is not None:
                try:
                    result = storage.upload_xml(
                        ctx.tenant_id,
                        ctx.execution_id,
                        item.nsu,
                        item.xml_bytes,
                    )
                    xml_key = result.object_key
                except StorageError as exc:
                    storage_errors += 1
                    logger.warning(
                        "jobs.run_execution.xml_upload_failed",
                        extra={
                            "execution_id": str(ctx.execution_id),
                            "nsu": item.nsu,
                            "error": str(exc),
                        },
                    )

            inserted = _insert_execution_item(ctx, item, xml_key)
            if not inserted:
                # Duplicata via unique `(tenant_id, chave_nfse)`. Nao conta
                # nem como ok nem como fail — e um retry idempotente.
                logger.info(
                    "jobs.run_execution.item_duplicate",
                    extra={
                        "execution_id": str(ctx.execution_id),
                        "chave_nfse": item.chave_nfse,
                        "nsu": item.nsu,
                    },
                )
                return

            if item.status == "ok":
                items_ok += 1
            else:
                items_fail += 1
        except Exception:  # noqa: BLE001 — loga e continua
            items_fail += 1
            logger.exception(
                "jobs.run_execution.progress_callback_error",
                extra={"execution_id": str(ctx.execution_id), "nsu": item.nsu},
            )

    def _on_log(evento: str, payload: dict) -> None:
        logger.info("jobs.fetch.%s", evento, extra={"payload": payload})

    try:
        summary = fetch_nfse(
            pfx_bytes=pfx_bytes,
            pfx_password=pfx_password,
            cnpj=ctx.cnpj,
            nsu_source=nsu_source,
            on_progress=_on_progress,
            on_log=_on_log,
        )
    except ValueError as exc:
        # mtls_session levanta ValueError para PFX invalido / senha errada /
        # cert vencido. Diferenciamos via mensagem para classificar ocorrencia.
        msg = str(exc).lower()
        code = OCC_CERT_EXPIRED if "vencid" in msg or "expir" in msg else OCC_CRED_INVALID
        _mark_failed(ctx, error_summary="mtls_session_failed")
        _create_occurrence(ctx, code=code, severity="error",
                           title="Falha na sessao mTLS", detail=str(exc))
        raise JobError("mtls_session_failed") from exc
    except Exception as exc:  # noqa: BLE001 — erro inesperado do coletor
        _mark_failed(ctx, error_summary="collector_error")
        _create_occurrence(ctx, code=OCC_UNKNOWN, severity="error",
                           title="Erro nao categorizado no coletor", detail=str(exc))
        raise JobError("collector_error") from exc

    final_status = _decide_final_status(summary, items_ok, items_fail, storage_errors)
    _mark_finished(
        ctx,
        status=final_status,
        summary=summary,
        items_ok=items_ok,
        items_fail=items_fail,
    )

    if storage_errors:
        _create_occurrence(
            ctx, code=OCC_STORAGE_ERROR, severity="warning",
            title=f"{storage_errors} XML(s) falharam no upload para S3",
            detail=f"storage_errors={storage_errors}",
        )
    if summary.fatal_rejected:
        _create_occurrence(
            ctx, code=OCC_PORTAL_5XX, severity="error",
            title="Portal ADN rejeitou a paginacao",
            detail="fatal_rejected=True",
        )
    if summary.total_erro:
        _create_occurrence(
            ctx, code=OCC_PARSE_ERROR, severity="warning",
            title=f"{summary.total_erro} XML(s) com parse_error",
            detail=f"total_erro={summary.total_erro}",
        )

    logger.info(
        "jobs.run_execution.ok",
        extra={
            "execution_id": str(ctx.execution_id),
            "tenant_id": str(ctx.tenant_id),
            "status": final_status,
            "items_ok": items_ok,
            "items_fail": items_fail,
            "storage_errors": storage_errors,
            "nsu_from": summary.nsu_from,
            "nsu_to": summary.nsu_to,
        },
    )

    return {
        "execution_id": str(ctx.execution_id),
        "status": final_status,
        "items_ok": items_ok,
        "items_fail": items_fail,
        "storage_errors": storage_errors,
        "nsu_from": summary.nsu_from,
        "nsu_to": summary.nsu_to,
    }


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _load_execution_context(execution_id: UUID) -> Optional[_ExecutionContext]:
    """Le tenant_id da execution (admin) e depois carrega o resto via RLS."""
    with get_admin_session() as session:
        row = session.execute(
            text(
                """
                SELECT id, tenant_id, company_id
                  FROM executions
                 WHERE id = :eid
                """
            ),
            {"eid": str(execution_id)},
        ).one_or_none()
        if row is None:
            return None
        tenant_id = UUID(str(row.tenant_id))
        company_id = UUID(str(row.company_id))

    with get_tenant_session(tenant_id) as session:
        company_row = session.execute(
            text("SELECT cnpj FROM companies WHERE id = :cid"),
            {"cid": str(company_id)},
        ).one_or_none()
        cred_row = session.execute(
            text(
                """
                SELECT id, pfx_object_key, pfx_password_ciphertext
                  FROM company_credentials
                 WHERE company_id = :cid
                   AND status = 'active'
                 ORDER BY created_at DESC
                 LIMIT 1
                """
            ),
            {"cid": str(company_id)},
        ).one_or_none()
        if company_row is None or cred_row is None:
            return None

    return _ExecutionContext(
        execution_id=execution_id,
        tenant_id=tenant_id,
        company_id=company_id,
        cnpj=str(company_row.cnpj),
        pfx_object_key=str(cred_row.pfx_object_key),
        pfx_password_ciphertext=bytes(cred_row.pfx_password_ciphertext),
        credential_id=UUID(str(cred_row.id)),
    )


def _mark_running(ctx: _ExecutionContext) -> None:
    with get_tenant_session(ctx.tenant_id) as session:
        session.execute(
            text(
                """
                UPDATE executions
                   SET status = 'running',
                       started_at = COALESCE(started_at, now()),
                       updated_at = now()
                 WHERE id = :eid
                """
            ),
            {"eid": str(ctx.execution_id)},
        )


def _mark_failed(ctx: _ExecutionContext, *, error_summary: str) -> None:
    try:
        with get_tenant_session(ctx.tenant_id) as session:
            session.execute(
                text(
                    """
                    UPDATE executions
                       SET status = 'failed',
                           finished_at = now(),
                           error_summary = :err,
                           updated_at = now()
                     WHERE id = :eid
                    """
                ),
                {"eid": str(ctx.execution_id), "err": error_summary},
            )
    except Exception:  # noqa: BLE001 — nao podemos mascarar a excecao original
        logger.exception(
            "jobs.run_execution.mark_failed_error",
            extra={"execution_id": str(ctx.execution_id)},
        )


def _mark_finished(
    ctx: _ExecutionContext,
    *,
    status: str,
    summary: FetchSummary,
    items_ok: int,
    items_fail: int,
) -> None:
    with get_tenant_session(ctx.tenant_id) as session:
        session.execute(
            text(
                """
                UPDATE executions
                   SET status = :st,
                       finished_at = now(),
                       nsu_from = :nsu_from,
                       nsu_to = :nsu_to,
                       items_total = :total,
                       items_ok = :ok,
                       items_fail = :fail,
                       updated_at = now()
                 WHERE id = :eid
                """
            ),
            {
                "st": status,
                "nsu_from": int(summary.nsu_from),
                "nsu_to": int(summary.nsu_to),
                "total": int(items_ok + items_fail),
                "ok": int(items_ok),
                "fail": int(items_fail),
                "eid": str(ctx.execution_id),
            },
        )


def _insert_execution_item(
    ctx: _ExecutionContext,
    item: NfseItem,
    xml_object_key: Optional[str],
) -> bool:
    """INSERT em `execution_items` com ON CONFLICT DO NOTHING.

    Retorna `True` quando a linha foi inserida e `False` quando a unique
    `(tenant_id, chave_nfse)` ja cobriu uma execucao anterior.
    """
    # Converte `status` do NfseItem ("ok"/"cancelada"/"parse_error") para
    # o dominio do CHECK `ck_execution_items_status` ("ok"/"failed"/
    # "skipped"/"pending"): cancelada -> skipped, parse_error -> failed.
    status_map = {"ok": "ok", "cancelada": "skipped", "parse_error": "failed"}
    item_status = status_map.get(item.status, "failed")

    with get_tenant_session(ctx.tenant_id) as session:
        inserted = session.execute(
            text(
                """
                INSERT INTO execution_items (
                    execution_id, tenant_id, nsu, chave_nfse,
                    cnpj_emitente, data_emissao, valor,
                    xml_object_key, status, error_code, error_message
                ) VALUES (
                    :eid,
                    NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                    :nsu, :chave,
                    :cnpj_em, :data_em, :valor,
                    :okey, :st, :ecode, :emsg
                )
                ON CONFLICT (tenant_id, chave_nfse)
                  WHERE chave_nfse IS NOT NULL
                  DO NOTHING
                RETURNING id
                """
            ),
            {
                "eid": str(ctx.execution_id),
                "nsu": int(item.nsu),
                "chave": item.chave_nfse,
                "cnpj_em": item.cnpj_emitente,
                "data_em": _parse_data_emissao(item.data_emissao),
                "valor": item.valor,
                "okey": xml_object_key,
                "st": item_status,
                "ecode": item.error_code,
                "emsg": item.error_message,
            },
        ).one_or_none()
    return inserted is not None


def _parse_data_emissao(value: Optional[str]):
    """Converte `DD/MM/AAAA` para ISO date; devolve None em falha."""
    if not value:
        return None
    try:
        dia, mes, ano = value.split("/")
        return f"{ano}-{int(mes):02d}-{int(dia):02d}"
    except (ValueError, AttributeError):
        return None


def _create_occurrence(
    ctx: _ExecutionContext,
    *,
    code: str,
    severity: str,
    title: str,
    detail: Optional[str] = None,
) -> None:
    try:
        with get_tenant_session(ctx.tenant_id) as session:
            session.execute(
                text(
                    """
                    INSERT INTO occurrences (
                        tenant_id, company_id, execution_id,
                        severity, code, title, detail, status
                    ) VALUES (
                        NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                        :cid, :eid, :sev, :code, :title, :detail, 'open'
                    )
                    """
                ),
                {
                    "cid": str(ctx.company_id),
                    "eid": str(ctx.execution_id),
                    "sev": severity,
                    "code": code,
                    "title": title,
                    "detail": detail,
                },
            )
    except Exception:  # noqa: BLE001 — ocorrencia e best-effort
        logger.exception(
            "jobs.run_execution.occurrence_insert_failed",
            extra={"execution_id": str(ctx.execution_id), "code": code},
        )


# ---------------------------------------------------------------------------
# Credential decrypt
# ---------------------------------------------------------------------------


def _decrypt_credential(
    ctx: _ExecutionContext,
    read_blob: Callable[[str], bytes],
) -> tuple[bytes, str]:
    """Le o blob cifrado no S3 e devolve `(pfx_bytes, pfx_password)`."""
    encrypted_pfx = read_blob(ctx.pfx_object_key)
    pfx_bytes = decrypt(encrypted_pfx, ctx.tenant_id)
    password_bytes = decrypt(ctx.pfx_password_ciphertext, ctx.tenant_id)
    return pfx_bytes, password_bytes.decode("utf-8")


def _default_read_credential_blob(object_key: str) -> bytes:
    """Le o blob no bucket default (mesmo usado pelo S3StorageClient)."""
    from worker_core.storage import S3Settings
    import boto3
    from botocore.client import Config as BotoConfig
    from botocore.exceptions import ClientError

    settings = S3Settings.from_env()
    kwargs = {
        "service_name": "s3",
        "region_name": settings.region or "us-east-1",
        "config": BotoConfig(
            s3={"addressing_style": "path" if settings.force_path_style else "auto"},
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    }
    if settings.endpoint:
        kwargs["endpoint_url"] = settings.endpoint
    if settings.key_id and settings.application_key:
        kwargs["aws_access_key_id"] = settings.key_id
        kwargs["aws_secret_access_key"] = settings.application_key
    client = boto3.client(**kwargs)
    try:
        resp = client.get_object(Bucket=settings.bucket, Key=object_key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        raise StorageError(
            f"falha ao ler credencial no storage (code={code!r})"
        ) from exc
    return resp["Body"].read()


# ---------------------------------------------------------------------------
# Status decision
# ---------------------------------------------------------------------------


def _decide_final_status(
    summary: FetchSummary,
    items_ok: int,
    items_fail: int,
    storage_errors: int,
) -> str:
    """Decide o status final a partir do resumo + contadores."""
    if summary.fatal_rejected:
        return "failed"
    if items_ok == 0 and items_fail == 0 and storage_errors == 0:
        # Nada coletado e sem falha — execucao "succeeded" vazia (sem NFSE
        # novas no periodo). `nsu_to == nsu_from` sinaliza isso.
        return "succeeded"
    if items_fail > 0 or storage_errors > 0:
        if items_ok == 0:
            return "failed"
        return "partial"
    return "succeeded"


def _coerce_uuid(value: str, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise JobError(f"{field} invalido: {value!r}") from exc
