"""Endpoints de `/executions` (API-07 + API-08).

- `POST /executions` (owner|admin|operator): valida companies +
  credenciais, cria 1 linha em `executions` por company na mesma
  transacao e enfileira 1 job RQ por execution. Pre-pinga o Redis
  antes do INSERT para evitar criar execucoes orfas quando a fila
  esta offline. Se o enqueue falhar apos o INSERT (ex.: Redis caiu
  no meio), a linha afetada e marcada como `failed` com
  `error_summary='enqueue_failed'` e devolvida com `job_id=None`.

- `GET /executions/{id}` (todos os papeis): devolve o detalhe
  completo (status, contadores agregados via `items_total`/`items_ok`/
  `items_fail`, NSU, periodo). RLS do `get_tenant_db` garante 404
  cross-tenant.

- `GET /executions` (todos os papeis): paginado, com filtros
  `company_id`, `status`, `from`/`to` (sobre `started_at`). Usa o
  indice `ix_executions_tenant_started` (0017) para ordenar por
  `started_at DESC NULLS LAST`. Quando `company_id` esta presente,
  o composto `ix_executions_tenant_company_started` (0004) entra.

- `GET /executions/{id}/items` (todos os papeis): paginado, com
  filtros `status`, `nsu`. Usa `ix_execution_items_execution_id`
  (0005) para reduzir a uma execucao antes de filtrar.

Relacao com outros tickets:

- API-03 fornece `get_tenant_db` (RLS via GUC);
- API-04 fornece `require_role`;
- API-06 popula `company_credentials` (consultada aqui para validar
  que a company tem credencial ativa e nao-vencida);
- API-13 picara os jobs que este endpoint enfileira.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    ExecutionItemListOut,
    ExecutionItemOut,
    ExecutionItemStatus,
    ExecutionListOut,
    ExecutionOut,
    ExecutionStatus,
)

logger = logging.getLogger("api.executions")

router = APIRouter(prefix="/executions", tags=["executions"])

_ReadAccess = require_role("owner", "admin", "operator", "viewer")
_CreateAccess = require_role("owner", "admin", "operator")


def _validate_companies(db: Session, company_ids: list[UUID]) -> dict[UUID, dict]:
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
    return {UUID(str(row.id)): {"cnpj": row.cnpj, "status": row.status} for row in rows}


def _validate_credentials(db: Session, company_ids: list[UUID]) -> dict[UUID, dict]:
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
    return {UUID(str(row.company_id)): {"cert_not_after": row.cert_not_after} for row in rows}


_EXECUTION_COLUMNS = (
    "id, tenant_id, company_id, trigger, triggered_by_user_id, "
    "period_start, period_end, status, started_at, finished_at, "
    "nsu_from, nsu_to, items_total, items_ok, items_fail, "
    "error_summary, created_at, updated_at"
)


_EXECUTION_ITEM_COLUMNS = (
    "id, tenant_id, execution_id, nsu, chave_nfse, cnpj_emitente, "
    "data_emissao, valor, xml_object_key, status, error_code, "
    "error_message, created_at, updated_at"
)


def query_executions(
    db: Session,
    *,
    page: int,
    page_size: int,
    company_id: Optional[UUID] = None,
    status_: Optional[ExecutionStatus] = None,
    from_: Optional[datetime] = None,
    to: Optional[datetime] = None,
) -> ExecutionListOut:
    """Listagem paginada de `executions` no tenant corrente.

    Reusada por `GET /executions` e por `GET /companies/{id}/executions`
    (atalho). RLS de `executions` ja injeta `WHERE tenant_id = GUC`,
    entao nao precisamos repetir aqui — a clausula extra e apenas para
    os filtros do usuario.
    """
    params: dict[str, object] = {
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    where: list[str] = []

    if company_id is not None:
        where.append("company_id = :company_id")
        params["company_id"] = str(company_id)
    if status_ is not None:
        where.append("status = :status")
        params["status"] = status_
    if from_ is not None:
        where.append("started_at >= :from_")
        params["from_"] = from_
    if to is not None:
        where.append("started_at < :to")
        params["to"] = to

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    total_row = db.execute(
        text(f"SELECT COUNT(*) AS n FROM executions{where_sql}"),
        params,
    ).one()

    rows = db.execute(
        text(
            f"""
            SELECT {_EXECUTION_COLUMNS}
              FROM executions
              {where_sql}
          ORDER BY started_at DESC NULLS LAST, id
             LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).all()

    return ExecutionListOut(
        items=[_row_to_out(r) for r in rows],
        page=page,
        page_size=page_size,
        total=int(total_row.n),
    )


def _row_to_item_out(row) -> ExecutionItemOut:
    return ExecutionItemOut(
        id=row.id,
        tenant_id=row.tenant_id,
        execution_id=row.execution_id,
        nsu=row.nsu,
        chave_nfse=row.chave_nfse,
        cnpj_emitente=row.cnpj_emitente,
        data_emissao=row.data_emissao,
        valor=row.valor,
        xml_object_key=row.xml_object_key,
        status=row.status,
        error_code=row.error_code,
        error_message=row.error_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _find_open_execution(
    db: Session,
    *,
    company_id: UUID,
    trigger: str,
    period_start,
    period_end,
) -> Optional[UUID]:
    """Retorna execution aberta equivalente para tornar retries idempotentes.

    A deduplicacao cobre o caso operacional mais perigoso: clientes HTTP ou
    schedulers repetindo a mesma janela enquanto uma execution ainda esta
    `queued`/`running`. A RLS da sessao tenant restringe a busca ao tenant
    corrente.
    """
    row = db.execute(
        text(
            """
            SELECT id
              FROM executions
             WHERE company_id = :cid
               AND trigger = :trigger
               AND period_start = :pstart
               AND period_end = :pend
               AND status IN ('queued', 'running')
             ORDER BY created_at DESC, id DESC
             LIMIT 1
            """
        ),
        {
            "cid": str(company_id),
            "trigger": trigger,
            "pstart": period_start,
            "pend": period_end,
        },
    ).one_or_none()
    if row is None:
        return None
    return UUID(str(row.id))


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
    created_rows: list[tuple[UUID, UUID, bool]] = []
    for company_id in payload.company_ids:
        existing_execution_id = _find_open_execution(
            db,
            company_id=company_id,
            trigger=payload.trigger,
            period_start=payload.period_start,
            period_end=payload.period_end,
        )
        if existing_execution_id is not None:
            created_rows.append((existing_execution_id, company_id, False))
            continue

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
        created_rows.append((UUID(str(row.id)), company_id, True))

    # 5. Enqueue pos-INSERT. Cada falha marca a linha como `failed`.
    results: list[CreatedExecution] = []
    for execution_id, company_id, should_enqueue in created_rows:
        if not should_enqueue:
            results.append(
                CreatedExecution(
                    execution_id=execution_id,
                    company_id=company_id,
                    status="queued",
                    job_id=None,
                    enqueue_error=None,
                )
            )
            continue

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
    "",
    response_model=ExecutionListOut,
    dependencies=[Depends(_ReadAccess)],
    summary="Lista execucoes do tenant (paginado, com filtros)",
)
def list_executions(
    db: Session = Depends(get_tenant_db),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
    company_id: Optional[UUID] = Query(default=None),
    status_: Optional[ExecutionStatus] = Query(default=None, alias="status"),
    from_: Optional[datetime] = Query(
        default=None,
        alias="from",
        description="Inicio do periodo (started_at >=). ISO 8601 UTC.",
    ),
    to: Optional[datetime] = Query(
        default=None,
        description="Fim do periodo (started_at <). ISO 8601 UTC.",
    ),
) -> ExecutionListOut:
    return query_executions(
        db,
        page=page,
        page_size=page_size,
        company_id=company_id,
        status_=status_,
        from_=from_,
        to=to,
    )


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


@router.get(
    "/{execution_id}/items",
    response_model=ExecutionItemListOut,
    dependencies=[Depends(_ReadAccess)],
    summary="Lista os items processados de uma execucao (paginado)",
)
def list_execution_items(
    execution_id: UUID,
    db: Session = Depends(get_tenant_db),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=50, ge=1, le=200),
    status_: Optional[ExecutionItemStatus] = Query(default=None, alias="status"),
    nsu: Optional[int] = Query(default=None, ge=0),
    scope: Literal["issued", "all"] = Query(
        default="issued",
        description="issued filtra pelo CNPJ emitente da empresa; all e diagnostico.",
    ),
) -> ExecutionItemListOut:
    # 404 antes de listar — RLS isola cross-tenant.
    parent = db.execute(
        text(
            """
            SELECT e.id, c.cnpj AS company_cnpj
              FROM executions e
              JOIN companies c
                ON c.id = e.company_id AND c.tenant_id = e.tenant_id
             WHERE e.id = :eid
            """
        ),
        {"eid": str(execution_id)},
    ).one_or_none()
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="execution nao encontrada",
        )

    params: dict[str, object] = {
        "eid": str(execution_id),
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    where: list[str] = ["execution_id = :eid"]
    if scope == "issued":
        where.append(
            "regexp_replace(COALESCE(cnpj_emitente, ''), '[^0-9]', '', 'g') = :company_cnpj"
        )
        params["company_cnpj"] = parent.company_cnpj
    if status_ is not None:
        where.append("status = :status")
        params["status"] = status_
    if nsu is not None:
        where.append("nsu = :nsu")
        params["nsu"] = nsu
    where_sql = " WHERE " + " AND ".join(where)

    total_row = db.execute(
        text(f"SELECT COUNT(*) AS n FROM execution_items{where_sql}"),
        params,
    ).one()

    rows = db.execute(
        text(
            f"""
            SELECT {_EXECUTION_ITEM_COLUMNS}
              FROM execution_items
              {where_sql}
          ORDER BY nsu ASC NULLS LAST, id
             LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).all()

    return ExecutionItemListOut(
        items=[_row_to_item_out(r) for r in rows],
        page=page,
        page_size=page_size,
        total=int(total_row.n),
    )
