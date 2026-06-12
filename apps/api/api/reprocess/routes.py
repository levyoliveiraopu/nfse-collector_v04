"""Endpoints de `/reprocess` (API-10).

- `POST /reprocess` (owner|admin|operator): aceita 3 escopos (items,
  NSUs, periodo) e resolve cada um em uma lista de tuplas
  `(company_id, period_start, period_end)`. Valida companies +
  credenciais ativas (reusa helpers de `executions/routes`), grava 1
  linha em `reprocess_jobs` (status `queued`, `scope` jsonb) + N
  `executions` filhas com `trigger='reprocess'` na mesma transacao e
  enfileira 1 job RQ por execution (reusa `enqueue_run_execution`).
  Pre-pinga o Redis antes do INSERT — fila offline aborta com 502 sem
  tocar DB.

- `GET /reprocess/{id}` (todos os papeis): devolve o registro + o
  `progress` derivado do JOIN com `executions` pelos ids em
  `result_execution_ids`. `effective_status` e computado em tempo de
  leitura porque o worker atual (API-13) nao atualiza
  `reprocess_jobs.status` — ticket futuro pode reconciliar.

Granularidade: o worker sempre refaz a janela inteira de
`(company, period_start, period_end)` da execution filha — o portal
Nacional pagina por NSU global e nao aceita lista de NSUs. A
idempotencia do unique parcial `uq_execution_items_tenant_chave`
(0005) garante que items ja `ok` nao duplicam; items `failed` voltam a
ser tentados. Escopos por item/NSU sao **refinamentos do pedido** (o
usuario filtra "o que quero retentar") que se traduzem em executions
filhas cobrindo o periodo dos alvos.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_tenant_db
from ..executions.routes import (
    _find_open_execution,
    _validate_companies,
    _validate_credentials,
)
from ..queue import QueueError, enqueue_run_execution, ping_redis
from ..security.jwt import AccessClaims
from ..security.rbac import require_role
from .schemas import (
    ReprocessChildExecution,
    ReprocessIn,
    ReprocessOut,
    ReprocessProgress,
)

logger = logging.getLogger("api.reprocess")

router = APIRouter(prefix="/reprocess", tags=["reprocess"])

_ReadAccess = require_role("owner", "admin", "operator", "viewer")
_WriteAccess = require_role("owner", "admin", "operator")


_REPROCESS_COLUMNS = (
    "id, tenant_id, created_by_user_id, scope, status, "
    "result_execution_ids, started_at, finished_at, error_summary, "
    "created_at, updated_at"
)


# ---------------------------------------------------------------------------
# Resolucao de escopo -> lista de (company_id, period_start, period_end)
# ---------------------------------------------------------------------------


def _resolve_by_items(db: Session, item_ids: list[UUID]) -> list[tuple[UUID, date, date]]:
    """Agrupa items pela execution-pai e devolve tuplas distintas.

    Items nao encontrados (RLS isola cross-tenant) geram 422 com a
    lista dos ids faltantes.
    """
    ids_str = [str(i) for i in item_ids]
    rows = db.execute(
        text(
            """
            SELECT i.id AS item_id,
                   e.company_id,
                   e.period_start,
                   e.period_end
              FROM execution_items i
              JOIN executions e ON e.id = i.execution_id
             WHERE i.id = ANY(:ids)
            """
        ),
        {"ids": ids_str},
    ).all()

    found_ids = {UUID(str(r.item_id)) for r in rows}
    missing = [i for i in item_ids if i not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "execution_items_not_found",
                "missing": [str(i) for i in missing],
            },
        )

    seen: set[tuple[UUID, date, date]] = set()
    tuples: list[tuple[UUID, date, date]] = []
    for r in rows:
        tup = (UUID(str(r.company_id)), r.period_start, r.period_end)
        if tup in seen:
            continue
        seen.add(tup)
        tuples.append(tup)
    return tuples


def _resolve_by_nsus(db: Session, company_id: UUID, nsus: list[int]) -> list[tuple[UUID, date, date]]:
    """Inferir periodo a partir de `MIN/MAX(data_emissao)` dos items.

    Fallback quando nenhum item bate: `[today, today]`. Isso cria uma
    execucao-filha de 1 dia — o worker refara a coleta nesse periodo e,
    se os NSUs ainda estiverem disponiveis no portal, eles sao recoletados.
    """
    row = db.execute(
        text(
            """
            SELECT MIN(data_emissao) AS min_d,
                   MAX(data_emissao) AS max_d
              FROM execution_items
             WHERE nsu = ANY(:nsus)
            """
        ),
        {"nsus": nsus},
    ).one()

    if row.min_d is None or row.max_d is None:
        today = date.today()
        return [(company_id, today, today)]

    start = row.min_d.date() if hasattr(row.min_d, "date") else row.min_d
    end = row.max_d.date() if hasattr(row.max_d, "date") else row.max_d
    if end < start:
        end = start
    return [(company_id, start, end)]


def _resolve_by_period(company_id: UUID, period_start: date, period_end: date) -> list[tuple[UUID, date, date]]:
    return [(company_id, period_start, period_end)]


# ---------------------------------------------------------------------------
# Mapeadores
# ---------------------------------------------------------------------------


def _row_to_out(row, *, scope: Optional[dict] = None) -> ReprocessOut:
    scope_value = scope if scope is not None else _scope_from_row(row.scope)
    return ReprocessOut(
        id=row.id,
        tenant_id=row.tenant_id,
        status=row.status,
        scope=scope_value,
        result_execution_ids=[UUID(str(x)) for x in (row.result_execution_ids or [])],
        error_summary=row.error_summary,
        created_by_user_id=row.created_by_user_id,
        started_at=row.started_at,
        finished_at=row.finished_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _scope_from_row(raw) -> dict:
    """`reprocess_jobs.scope` volta como `dict` (psycopg3) ou `str` (driver legado)."""
    if raw is None:
        return {}
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw


def _audit_create(
    db: Session,
    *,
    actor_user_id: UUID,
    request: Request,
    reprocess_job_id: UUID,
    scope_kind: str,
    executions_count: int,
    dry_run: bool,
) -> None:
    """Grava `audit_logs.action='reprocess.create'` sem vazar dados sensiveis."""
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    metadata = {
        "scope_kind": scope_kind,
        "executions_count": executions_count,
        "dry_run": bool(dry_run),
    }
    db.execute(
        text(
            """
            INSERT INTO audit_logs (
                tenant_id, actor_user_id, action,
                resource_type, resource_id,
                ip, user_agent, metadata
            ) VALUES (
                NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                :uid, 'reprocess.create',
                'reprocess_job', :rid,
                CAST(:ip AS inet), :ua, CAST(:meta AS jsonb)
            )
            """
        ),
        {
            "uid": str(actor_user_id),
            "rid": str(reprocess_job_id),
            "ip": ip,
            "ua": user_agent,
            "meta": json.dumps(metadata, default=str, separators=(",", ":")),
        },
    )


# ---------------------------------------------------------------------------
# POST /reprocess
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ReprocessOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cria um reprocess_job + executions filhas e enfileira no Redis",
)
def create_reprocess(
    payload: ReprocessIn,
    request: Request,
    db: Session = Depends(get_tenant_db),
    claims: AccessClaims = Depends(_WriteAccess),
) -> ReprocessOut:
    # 1. Resolve o escopo em tuplas (company_id, period_start, period_end).
    scope_kind = payload.scope_kind()
    if scope_kind == "items":
        assert payload.execution_item_ids is not None
        tuples = _resolve_by_items(db, payload.execution_item_ids)
    elif scope_kind == "nsus":
        assert payload.company_id is not None and payload.nsus is not None
        tuples = _resolve_by_nsus(db, payload.company_id, payload.nsus)
    else:
        assert payload.company_id is not None and payload.period is not None
        tuples = _resolve_by_period(payload.company_id, payload.period.start, payload.period.end)

    if not tuples:
        # Defensivo — os resolvers sempre devolvem >=1 tupla hoje.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "empty_scope"},
        )

    # 2. Valida companies (RLS) + credenciais ativas.
    company_ids = sorted({cid for cid, _, _ in tuples}, key=str)
    companies = _validate_companies(db, company_ids)
    missing = [cid for cid in company_ids if cid not in companies]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "companies_not_found",
                "missing": [str(cid) for cid in missing],
            },
        )

    creds = _validate_credentials(db, company_ids)
    without_cred = [cid for cid in company_ids if cid not in creds]
    if without_cred:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "credential_missing_or_expired",
                "company_ids": [str(cid) for cid in without_cred],
            },
        )

    # 3. Pre-ping Redis: se offline, aborta sem tocar DB.
    try:
        ping_redis()
    except QueueError as exc:
        logger.warning(
            "reprocess.create.redis_down",
            extra={"tenant_id": str(claims.tid), "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="fila de jobs indisponivel",
        ) from exc

    # 4. Cria reprocess_jobs + N executions filhas na mesma transacao.
    scope_json = payload.to_scope_json()
    job_row = db.execute(
        text(
            """
            INSERT INTO reprocess_jobs (
                tenant_id, created_by_user_id, scope, status
            ) VALUES (
                NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                :uid, CAST(:scope AS jsonb), 'queued'
            )
            RETURNING id
            """
        ),
        {
            "uid": str(claims.sub),
            "scope": json.dumps(scope_json, default=str, separators=(",", ":")),
        },
    ).one()
    reprocess_job_id = UUID(str(job_row.id))

    created_children: list[tuple[UUID, UUID, date, date, bool]] = []
    for company_id, period_start, period_end in tuples:
        existing_execution_id = _find_open_execution(
            db,
            company_id=company_id,
            trigger="reprocess",
            period_start=period_start,
            period_end=period_end,
        )
        if existing_execution_id is not None:
            created_children.append((existing_execution_id, company_id, period_start, period_end, False))
            continue

        row = db.execute(
            text(
                """
                INSERT INTO executions (
                    tenant_id, company_id, trigger, triggered_by_user_id,
                    period_start, period_end, status
                ) VALUES (
                    NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                    :cid, 'reprocess', :uid,
                    :pstart, :pend, 'queued'
                )
                RETURNING id
                """
            ),
            {
                "cid": str(company_id),
                "uid": str(claims.sub),
                "pstart": period_start,
                "pend": period_end,
            },
        ).one()
        created_children.append((UUID(str(row.id)), company_id, period_start, period_end, True))

    # 5. Persiste result_execution_ids.
    db.execute(
        text(
            """
            UPDATE reprocess_jobs
               SET result_execution_ids = :ids,
                   updated_at = now()
             WHERE id = :rid
            """
        ),
        {
            "rid": str(reprocess_job_id),
            "ids": [str(eid) for eid, _, _, _, _ in created_children],
        },
    )

    # 6. Enqueue pos-INSERT. Cada falha marca a execution filha como
    # `failed`. Se todas falharem, registra `error_summary` no job-pai.
    results: list[ReprocessChildExecution] = []
    enqueue_failures = 0
    for execution_id, company_id, period_start, period_end, should_enqueue in created_children:
        if not should_enqueue:
            results.append(
                ReprocessChildExecution(
                    execution_id=execution_id,
                    company_id=company_id,
                    period_start=period_start,
                    period_end=period_end,
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
            enqueue_failures += 1
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
                "reprocess.create.enqueue_failed",
                extra={
                    "execution_id": str(execution_id),
                    "company_id": str(company_id),
                    "error": str(exc),
                },
            )
            results.append(
                ReprocessChildExecution(
                    execution_id=execution_id,
                    company_id=company_id,
                    period_start=period_start,
                    period_end=period_end,
                    status="failed",
                    job_id=None,
                    enqueue_error="enqueue_failed",
                )
            )
            continue

        results.append(
            ReprocessChildExecution(
                execution_id=execution_id,
                company_id=company_id,
                period_start=period_start,
                period_end=period_end,
                status="queued",
                job_id=job_id,
                enqueue_error=None,
            )
        )

    if enqueue_failures > 0 and enqueue_failures == len(created_children):
        db.execute(
            text(
                """
                UPDATE reprocess_jobs
                   SET status = 'failed',
                       error_summary = 'enqueue_failed_all',
                       finished_at = now(),
                       updated_at = now()
                 WHERE id = :rid
                """
            ),
            {"rid": str(reprocess_job_id)},
        )

    # 7. Audit.
    _audit_create(
        db,
        actor_user_id=claims.sub,
        request=request,
        reprocess_job_id=reprocess_job_id,
        scope_kind=scope_kind,
        executions_count=len(created_children),
        dry_run=payload.dry_run,
    )

    logger.info(
        "reprocess.create.ok",
        extra={
            "tenant_id": str(claims.tid),
            "reprocess_job_id": str(reprocess_job_id),
            "scope_kind": scope_kind,
            "executions": len(created_children),
            "enqueue_failures": enqueue_failures,
            "dry_run": payload.dry_run,
        },
    )

    # 8. Devolve a leitura atualizada do job + metadados fresh.
    row = db.execute(
        text(f"SELECT {_REPROCESS_COLUMNS} FROM reprocess_jobs WHERE id = :rid"),
        {"rid": str(reprocess_job_id)},
    ).one()
    out = _row_to_out(row, scope=scope_json)
    out.created_executions = results
    return out


# ---------------------------------------------------------------------------
# GET /reprocess/{id}
# ---------------------------------------------------------------------------


@router.get(
    "/{reprocess_job_id}",
    response_model=ReprocessOut,
    dependencies=[Depends(_ReadAccess)],
    summary="Detalha um reprocess_job + progresso agregado das executions",
)
def get_reprocess(
    reprocess_job_id: UUID,
    db: Session = Depends(get_tenant_db),
) -> ReprocessOut:
    row = db.execute(
        text(f"SELECT {_REPROCESS_COLUMNS} FROM reprocess_jobs WHERE id = :rid"),
        {"rid": str(reprocess_job_id)},
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="reprocess_job nao encontrado",
        )

    out = _row_to_out(row)

    # Progresso derivado do JOIN com executions.
    if out.result_execution_ids:
        exec_ids = [str(i) for i in out.result_execution_ids]
        counts_row = db.execute(
            text(
                """
                SELECT status, COUNT(*) AS n
                  FROM executions
                 WHERE id = ANY(:ids)
              GROUP BY status
                """
            ),
            {"ids": exec_ids},
        ).all()
        counts: dict[str, int] = {r.status: int(r.n) for r in counts_row}
    else:
        counts = {}

    total = len(out.result_execution_ids)
    queued = counts.get("queued", 0)
    running = counts.get("running", 0)
    succeeded = counts.get("succeeded", 0)
    failed = counts.get("failed", 0)
    cancelled = counts.get("cancelled", 0)
    partial = counts.get("partial", 0)

    effective = _effective_status(
        total=total,
        queued=queued,
        running=running,
        succeeded=succeeded,
        failed=failed,
        cancelled=cancelled,
        partial=partial,
    )

    out.progress = ReprocessProgress(
        total=total,
        queued=queued,
        running=running,
        succeeded=succeeded,
        failed=failed,
        cancelled=cancelled,
        partial=partial,
        effective_status=effective,
    )
    return out


def _effective_status(
    *,
    total: int,
    queued: int,
    running: int,
    succeeded: int,
    failed: int,
    cancelled: int,
    partial: int,
) -> str:
    """Agrega status das executions filhas num rotulo efetivo.

    Regras:
    - `total == 0` (job recem-criado sem filhas — defensivo) -> `queued`.
    - qualquer `running` ou `queued` -> `running` (work in progress).
    - todas terminaram:
        * qualquer `partial` -> `partial`;
        * qualquer `failed` sem sucesso -> `failed`;
        * mistura sucesso+falha -> `partial`;
        * so sucesso -> `succeeded`;
        * so cancelada -> `cancelled`.
    """
    if total == 0:
        return "queued"
    if queued > 0 or running > 0:
        return "running"
    if partial > 0:
        return "partial"
    if failed > 0 and succeeded > 0:
        return "partial"
    if failed > 0:
        return "failed"
    if cancelled == total:
        return "cancelled"
    if succeeded > 0:
        return "succeeded"
    return "cancelled"
