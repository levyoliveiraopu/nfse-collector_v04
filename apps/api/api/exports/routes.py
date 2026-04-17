"""Endpoints de `/exports` (API-15 — export ZIP assincrono).

- `POST /exports` (owner|admin|operator): valida company+periodo,
  pre-pinga Redis, insere 1 linha em `exports` com `status='queued'`
  e enfileira `worker_core.jobs.build_export(export_id)` via RQ.
  Em enqueue-fail pos-INSERT, marca a linha como `failed`.

- `GET /exports/{id}` (todos os papeis): devolve status. Quando
  `status='ready'` e `file_id` esta populado, gera URL pre-assinada
  1h (mesmo TTL de API-11) e inclui no envelope. RLS garante 404
  cross-tenant.

A geracao da URL audita em `audit_logs.action='export.download_url'`
com metadata publica — a URL em si NUNCA e persistida nem logada.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_tenant_db
from ..queue import QueueError, ping_redis
from ..security.jwt import AccessClaims
from ..security.rbac import require_role
from ..storage import StorageError, generate_presigned_get_url
from .schemas import CreateExportIn, CreateExportOut, ExportOut

logger = logging.getLogger("api.exports")

router = APIRouter(prefix="/exports", tags=["exports"])

_ReadAccess = require_role("owner", "admin", "operator", "viewer")
_CreateAccess = require_role("owner", "admin", "operator")

# TTL fixo da URL pre-assinada — alinhado com API-11.
_PRESIGN_TTL_SECONDS = 3600

_EXPORT_COLUMNS = (
    "e.id, e.tenant_id, e.company_id, e.requested_by_user_id, e.kind, "
    "e.period_start, e.period_end, e.status, e.file_id, e.items_count, "
    "e.total_bytes, e.error_code, e.error_message, e.started_at, "
    "e.finished_at, e.created_at, e.updated_at"
)


def _row_to_out(row, *, download_url: str | None = None,
                expires_in: int | None = None) -> ExportOut:
    return ExportOut(
        id=row.id,
        tenant_id=row.tenant_id,
        company_id=row.company_id,
        requested_by_user_id=row.requested_by_user_id,
        kind=row.kind,
        period_start=row.period_start,
        period_end=row.period_end,
        status=row.status,
        file_id=row.file_id,
        items_count=row.items_count,
        total_bytes=row.total_bytes,
        error_code=row.error_code,
        error_message=row.error_message,
        started_at=row.started_at,
        finished_at=row.finished_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        download_url=download_url,
        expires_in=expires_in,
    )


def _enqueue_build_export(
    export_id: UUID, *, tenant_id: UUID
) -> str:
    """Enfileira `worker_core.jobs.build_export(export_id)` no RQ.

    Mantemos a logica de enfileirar aqui em vez de em `api.queue`
    porque `queue.enqueue_run_execution` e especifico de executions.
    Se crescer, extraimos para um helper generico no proximo ticket
    do worker.
    """
    from ..queue import QueueError, get_queue

    try:
        queue = get_queue()
        job = queue.enqueue(
            "worker_core.jobs.build_export",
            str(export_id),
            job_timeout=2 * 60 * 60,  # 2h: export pode baixar muitos XMLs
            result_ttl=60 * 60 * 24,
            failure_ttl=60 * 60 * 24 * 7,
            meta={"tenant_id": str(tenant_id)},
        )
    except QueueError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "exports.enqueue_failed",
            extra={"export_id": str(export_id), "error": str(exc)},
        )
        raise QueueError("falha ao enfileirar job de export") from exc

    return str(getattr(job, "id", "") or "")


@router.post(
    "",
    response_model=CreateExportOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cria pedido de export e enfileira job assincrono",
)
def create_export(
    payload: CreateExportIn,
    db: Session = Depends(get_tenant_db),
    claims: AccessClaims = Depends(_CreateAccess),
) -> CreateExportOut:
    # 1. Valida company (RLS garante isolamento cross-tenant).
    company_row = db.execute(
        text(
            """
            SELECT id FROM companies
             WHERE id = :cid AND deleted_at IS NULL
            """
        ),
        {"cid": str(payload.company_id)},
    ).one_or_none()
    if company_row is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "company_not_found",
                "company_id": str(payload.company_id),
            },
        )

    # 2. Pre-ping do Redis: se offline, aborta antes de tocar o DB.
    try:
        ping_redis()
    except QueueError as exc:
        logger.warning(
            "exports.create.redis_down",
            extra={"tenant_id": str(claims.tid), "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="fila de jobs indisponivel",
        ) from exc

    # 3. INSERT em `exports`.
    inserted = db.execute(
        text(
            """
            INSERT INTO exports (
                tenant_id, company_id, requested_by_user_id,
                kind, period_start, period_end, status
            ) VALUES (
                NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                :cid, :uid, :kind, :pstart, :pend, 'queued'
            )
            RETURNING id
            """
        ),
        {
            "cid": str(payload.company_id),
            "uid": str(claims.sub),
            "kind": payload.kind,
            "pstart": payload.period_start,
            "pend": payload.period_end,
        },
    ).one()
    export_id = UUID(str(inserted.id))

    # 4. Enqueue. Em falha, marca a linha como `failed`.
    try:
        job_id = _enqueue_build_export(export_id, tenant_id=claims.tid)
    except QueueError as exc:
        db.execute(
            text(
                """
                UPDATE exports
                   SET status = 'failed',
                       error_code = 'enqueue_failed',
                       error_message = :msg,
                       finished_at = now(),
                       updated_at = now()
                 WHERE id = :eid
                """
            ),
            {"eid": str(export_id), "msg": str(exc)[:500]},
        )
        logger.warning(
            "exports.create.enqueue_failed",
            extra={
                "export_id": str(export_id),
                "tenant_id": str(claims.tid),
                "error": str(exc),
            },
        )
        return CreateExportOut(
            export_id=export_id,
            status="failed",
            job_id=None,
            enqueue_error="enqueue_failed",
        )

    logger.info(
        "exports.create.ok",
        extra={
            "export_id": str(export_id),
            "tenant_id": str(claims.tid),
            "company_id": str(payload.company_id),
            "kind": payload.kind,
            "job_id": job_id,
        },
    )
    return CreateExportOut(
        export_id=export_id,
        status="queued",
        job_id=job_id,
        enqueue_error=None,
    )


def _audit_download_url(
    db: Session,
    *,
    tenant_id: UUID,
    actor_user_id: UUID,
    export_id: UUID,
    file_id: UUID,
    object_key: str,
    size_bytes: int,
    expires_in: int,
    request: Request,
) -> None:
    """Grava audit de geracao de URL pre-assinada para um export.

    Nunca persiste a URL em si — ela e credencial temporaria.
    """
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    metadata = {
        "export_id": str(export_id),
        "file_id": str(file_id),
        "object_key": object_key,
        "bytes": size_bytes,
        "expires_in": expires_in,
    }
    db.execute(
        text(
            """
            INSERT INTO audit_logs (
                tenant_id, actor_user_id, action,
                resource_type, resource_id,
                ip, user_agent, metadata
            ) VALUES (
                :tid, :uid, 'export.download_url',
                'export', :rid,
                CAST(:ip AS inet), :ua, CAST(:meta AS jsonb)
            )
            """
        ),
        {
            "tid": str(tenant_id),
            "uid": str(actor_user_id),
            "rid": str(export_id),
            "ip": ip,
            "ua": user_agent,
            "meta": json.dumps(metadata, default=str, separators=(",", ":")),
        },
    )


@router.get(
    "/{export_id}",
    response_model=ExportOut,
    summary="Status do export (inclui URL pre-assinada quando pronto)",
)
def get_export(
    export_id: UUID,
    request: Request,
    db: Session = Depends(get_tenant_db),
    claims: AccessClaims = Depends(_ReadAccess),
) -> ExportOut:
    # Join opcional em `files` para extrair object_key+bytes quando
    # ha artefato pronto. RLS em `exports` garante isolamento; RLS em
    # `files` tambem, mas o JOIN e dentro da mesma conexao/tenant.
    row = db.execute(
        text(
            f"""
            SELECT {_EXPORT_COLUMNS},
                   f.object_key AS file_object_key,
                   f.bytes      AS file_bytes
              FROM exports e
         LEFT JOIN files f ON f.id = e.file_id
                          AND f.tenant_id = e.tenant_id
             WHERE e.id = :eid
            """
        ),
        {"eid": str(export_id)},
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="export nao encontrado",
        )

    download_url: str | None = None
    expires_in: int | None = None

    if row.status == "ready" and row.file_id and row.file_object_key:
        try:
            download_url = generate_presigned_get_url(
                row.file_object_key,
                expires_seconds=_PRESIGN_TTL_SECONDS,
            )
            expires_in = _PRESIGN_TTL_SECONDS
        except StorageError as exc:
            logger.error(
                "exports.url.presign_failed",
                extra={
                    "tenant_id": str(claims.tid),
                    "export_id": str(export_id),
                    "object_key": row.file_object_key,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="falha ao gerar URL pre-assinada",
            ) from exc

        _audit_download_url(
            db,
            tenant_id=claims.tid,
            actor_user_id=claims.sub,
            export_id=row.id,
            file_id=row.file_id,
            object_key=row.file_object_key,
            size_bytes=int(row.file_bytes or 0),
            expires_in=_PRESIGN_TTL_SECONDS,
            request=request,
        )

        logger.info(
            "exports.url.issued",
            extra={
                "tenant_id": str(claims.tid),
                "export_id": str(export_id),
                "expires_in": _PRESIGN_TTL_SECONDS,
            },
        )

    return _row_to_out(row, download_url=download_url, expires_in=expires_in)
