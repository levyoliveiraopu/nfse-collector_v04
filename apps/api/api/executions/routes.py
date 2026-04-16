"""Endpoints de `/executions` (API-07).

- `POST /executions` (owner|admin|operator): valida companies +
  credenciais, cria 1 linha em `executions` por company na mesma
  transacao e enfileira 1 job RQ por execution. Pre-pinga o Redis
  antes do INSERT para evitar criar execucoes orfas quando a fila
  esta offline. Se o enqueue falhar apos o INSERT (ex.: Redis caiu
  no meio), a linha afetada e marcada como `failed` com
  `error_summary='enqueue_failed'` e devolvida com `job_id=None`.

- `GET /executions/{id}` (todos os papeis): devolve o detalhe
  completo (status, contadores, NSU, periodo). RLS do
  `get_tenant_db` garante 404 cross-tenant.

Relacao com outros tickets:

- API-03 fornece `get_tenant_db` (RLS via GUC);
- API-04 fornece `require_role`;
- API-06 popula `company_credentials` (consultada aqui para validar
  que a company tem credencial ativa e nao-vencida);
- API-13 picara os jobs que este endpoint enfileira.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_tenant_db
from ..queue import QueueError, enqueue_run_execution, ping_redis
from ..security.jwt import AccessClaims
from ..security.rbac import require_role
from .schemas import (
    CreateExecutionsIn,
    CreateExecutionsOut,
    CreatedExecution,
    ExecutionOut,
)

logger = logging.getLogger("api.executions")

router = APIRouter(prefix="/executions", tags=["executions"])

_ReadAccess = require_role("owner", "admin", "operator", "viewer")
_CreateAccess = require_role("owner", "admin", "operator")


def _validate_companies(
    db: Session, company_ids: list[UUID]
) -> dict[UUID, dict]:
    """Devolve `{company_id: {cnpj, status}}` para companies vivas no tenant.

    Companies que nao pertencem ao tenant (filtradas por RLS) ou estao
    soft-deleted simplesmente nao aparecem no dicionario — o handler
    trata o conjunto faltante como "nao encontrada".
    """
    if not company_ids:
        return {}

    ids_str = [str(cid) for cid in company_ids]
    rows = db.execute(
        text(
            """
            SELECT id, cnpj, status
              FROM companies
             WHERE id = ANY(:ids) AND deleted_at IS NULL
            """
        ),
        {"ids": ids_str},
    ).all()
    return {
        UUID(str(row.id)): {"cnpj": row.cnpj, "status": row.status}
        for row in rows
    }


def _validate_credentials(
    db: Session, company_ids: list[UUID]
) -> dict[UUID, dict]:
    """Devolve `{company_id: {cert_not_after}}` das companies com credencial ativa.

    Considera valida a credencial com `status='active'` E
    `cert_not_after IS NOT NULL AND cert_not_after > now()`. Companies
    sem credencial ativa (ou com cert vencido) ficam fora do dicionario.
    """
    if not company_ids:
        return {}
    ids_str = [str(cid) for cid in company_ids]
    rows = db.execute(
        text(
            """
            SELECT company_id, cert_not_after
              FROM company_credentials
             WHERE company_id = ANY(:ids)
               AND status = 'active'
               AND cert_not_after IS NOT NULL
               AND cert_not_after > now()
            """
        ),
        {"ids": ids_str},
    ).all()
    return {
        UUID(str(row.company_id)): {"cert_not_after": row.cert_not_after}
        for row in rows
    }


_EXECUTION_COLUMNS = (
    "id, tenant_id, company_id, trigger, triggered_by_user_id, "
    "period_start, period_end, status, started_at, finished_at, "
    "nsu_from, nsu_to, items_total, items_ok, items_fail, "
    "error_summary, created_at, updated_at"
)


def _row_to_out(row) -> ExecutionOut:
    return ExecutionOut(
        id=row.id,
        tenant_id=row.tenant_id,
        company_id=row.company_id,
        trigger=row.trigger,
        status=row.status,
        period_start=row.period_start,
        period_end=row.period_end,
        started_at=row.started_at,
        finished_at=row.finished_at,
        nsu_from=row.nsu_from,
        nsu_to=row.nsu_to,
        items_total=row.items_total,
        items_ok=row.items_ok,
        items_fail=row.items_fail,
        error_summary=row.error_summary,
        triggered_by_user_id=row.triggered_by_user_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post(
    "",
    response_model=CreateExecutionsOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cria N execucoes (1 por company) e enfileira no Redis",
)
def create_executions(
    payload: CreateExecutionsIn,
    db: Session = Depends(get_tenant_db),
    claims: AccessClaims = Depends(_CreateAccess),
) -> CreateExecutionsOut:
    # 1. Valida companies (RLS garante que so enxergamos do tenant).
    companies = _validate_companies(db, payload.company_ids)
    missing = [cid for cid in payload.company_ids if cid not in companies]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "companies_not_found",
                "missing": [str(cid) for cid in missing],
            },
        )

    # 2. Valida credenciais (ativa + nao-vencida).
    creds = _validate_credentials(db, payload.company_ids)
    without_cred = [cid for cid in payload.company_ids if cid not in creds]
    if without_cred:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "credential_missing_or_expired",
                "company_ids": [str(cid) for cid in without_cred],
            },
        )

    # 3. Pre-ping do Redis: se offline, aborta sem tocar o DB.
    try:
        ping_redis()
    except QueueError as exc:
        logger.warning(
            "executions.create.redis_down",
            extra={"tenant_id": str(claims.tid), "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="fila de jobs indisponivel",
        ) from exc

    # 4. INSERTs em transacao unica (get_tenant_db ja abriu tx).
    created_rows: list[tuple[UUID, UUID]] = []
    for company_id in payload.company_ids:
        row = db.execute(
            text(
                """
                INSERT INTO executions (
                    tenant_id, company_id, trigger, triggered_by_user_id,
                    period_start, period_end, status
                ) VALUES (
                    NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                    :cid, :trigger, :uid,
                    :pstart, :pend, 'queued'
                )
                RETURNING id
                """
            ),
            {
                "cid": str(company_id),
                "trigger": payload.trigger,
                "uid": str(claims.sub),
                "pstart": payload.period_start,
                "pend": payload.period_end,
            },
        ).one()
        created_rows.append((UUID(str(row.id)), company_id))

    # 5. Enqueue pos-INSERT. Cada falha marca a linha como `failed`.
    results: list[CreatedExecution] = []
    for execution_id, company_id in created_rows:
        try:
            job_id = enqueue_run_execution(
                execution_id,
                tenant_id=claims.tid,
                dry_run=payload.dry_run,
            )
        except QueueError as exc:
            # Marca a execution como falhada no mesmo tx. `finished_at`
            # fica com now() para evitar confundir com queued.
            db.execute(
                text(
                    """
                    UPDATE executions
                       SET status = 'failed',
                           error_summary = 'enqueue_failed',
                           finished_at = now(),
                           updated_at = now()
                     WHERE id = :eid
                    """
                ),
                {"eid": str(execution_id)},
            )
            logger.warning(
                "executions.create.enqueue_failed",
                extra={
                    "execution_id": str(execution_id),
                    "company_id": str(company_id),
                    "error": str(exc),
                },
            )
            results.append(
                CreatedExecution(
                    execution_id=execution_id,
                    company_id=company_id,
                    status="failed",
                    job_id=None,
                    enqueue_error="enqueue_failed",
                )
            )
            continue

        results.append(
            CreatedExecution(
                execution_id=execution_id,
                company_id=company_id,
                status="queued",
                job_id=job_id,
                enqueue_error=None,
            )
        )

    logger.info(
        "executions.create.ok",
        extra={
            "tenant_id": str(claims.tid),
            "count": len(results),
            "queued": sum(1 for r in results if r.status == "queued"),
            "failed": sum(1 for r in results if r.status == "failed"),
            "trigger": payload.trigger,
            "dry_run": payload.dry_run,
        },
    )
    return CreateExecutionsOut(created=results)


@router.get(
    "/{execution_id}",
    response_model=ExecutionOut,
    dependencies=[Depends(_ReadAccess)],
)
def get_execution(
    execution_id: UUID,
    db: Session = Depends(get_tenant_db),
) -> ExecutionOut:
    row = db.execute(
        text(f"SELECT {_EXECUTION_COLUMNS} FROM executions WHERE id = :eid"),
        {"eid": str(execution_id)},
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="execution nao encontrada",
        )
    return _row_to_out(row)
