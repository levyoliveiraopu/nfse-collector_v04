"""Endpoints de `/occurrences` (API-09).

Inbox de ocorrencias operacionais por tenant. Schema da tabela em
`apps/api/alembic/versions/0006_occurrences.py` (DATA-04). Todos os
handlers passam por `get_tenant_db` (RLS via GUC `app.current_tenant`)
e por `require_role` segundo a matriz em
`docs/architecture/rbac-matrix.md`:

- `GET`                  : todos (min_role=viewer)
- `POST .../acknowledge` : owner, admin, operator
- `POST .../resolve`     : owner, admin, operator
- `POST .../assign`      : owner, admin, operator

Cada acao mutadora grava uma linha em `audit_logs` com
`action='occurrence.<verb>'`, `resource_type='occurrence'` e metadata
publico (status_from/status_to, note, assignee_user_id, etc.). Sem
segredos.
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_tenant_db
from ..security.jwt import AccessClaims
from ..security.rbac import require_role
from .schemas import (
    OccurrenceAssignIn,
    OccurrenceListOut,
    OccurrenceOut,
    OccurrenceResolveIn,
    OccurrenceSeverity,
    OccurrenceStatus,
)

logger = logging.getLogger("api.occurrences")

router = APIRouter(prefix="/occurrences", tags=["occurrences"])

_ReadAccess = require_role("owner", "admin", "operator", "viewer")
_WriteAccess = require_role("owner", "admin", "operator")

_COLUMNS = (
    "id, tenant_id, company_id, execution_id, severity, code, title, "
    "detail, status, assignee_user_id, first_seen_at, last_seen_at, "
    "resolved_at, created_at, updated_at"
)

# Status considerados "fechados" — bloqueiam acknowledge e novas
# transicoes que nao sejam re-resolve idempotente.
_TERMINAL_STATUSES = frozenset({"resolved", "ignored"})


def _row_to_out(row) -> OccurrenceOut:
    return OccurrenceOut(
        id=row.id,
        tenant_id=row.tenant_id,
        company_id=row.company_id,
        execution_id=row.execution_id,
        severity=row.severity,
        code=row.code,
        title=row.title,
        detail=row.detail,
        status=row.status,
        assignee_user_id=row.assignee_user_id,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        resolved_at=row.resolved_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _fetch_occurrence(db: Session, occurrence_id: UUID) -> OccurrenceOut:
    """Busca uma ocorrencia ou levanta 404 (RLS isola cross-tenant)."""
    row = db.execute(
        text(f"SELECT {_COLUMNS} FROM occurrences WHERE id = :oid"),
        {"oid": str(occurrence_id)},
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ocorrencia nao encontrada",
        )
    return _row_to_out(row)


def _audit(
    db: Session,
    *,
    actor_user_id: UUID,
    action: str,
    resource_id: str,
    request: Request,
    metadata: dict,
) -> None:
    """Insere `audit_logs` para a acao do tenant corrente.

    `tenant_id` e injetado pela RLS (`WITH CHECK` da policy garante que
    o INSERT bate com a GUC). Mantemos o INSERT explicito com a GUC
    para nao depender de default — `audit_logs.tenant_id` e NOT NULL.
    """
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    db.execute(
        text(
            """
            INSERT INTO audit_logs (
                tenant_id, actor_user_id, action,
                resource_type, resource_id,
                ip, user_agent, metadata
            ) VALUES (
                NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                :uid, :action,
                'occurrence', :rid,
                CAST(:ip AS inet), :ua, CAST(:meta AS jsonb)
            )
            """
        ),
        {
            "uid": str(actor_user_id),
            "action": action,
            "rid": resource_id,
            "ip": ip,
            "ua": user_agent,
            "meta": json.dumps(metadata, default=str, separators=(",", ":")),
        },
    )


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=OccurrenceListOut,
    dependencies=[Depends(_ReadAccess)],
)
def list_occurrences(
    db: Session = Depends(get_tenant_db),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
    status_: Optional[OccurrenceStatus] = Query(default=None, alias="status"),
    severity: Optional[OccurrenceSeverity] = Query(default=None),
    company_id: Optional[UUID] = Query(default=None),
) -> OccurrenceListOut:
    params: dict[str, object] = {
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    where: list[str] = []
    if status_ is not None:
        where.append("status = :status")
        params["status"] = status_
    if severity is not None:
        where.append("severity = :severity")
        params["severity"] = severity
    if company_id is not None:
        where.append("company_id = :cid")
        params["cid"] = str(company_id)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    total_row = db.execute(
        text(f"SELECT COUNT(*) AS n FROM occurrences{where_sql}"),
        params,
    ).one()

    rows = db.execute(
        text(
            f"""
            SELECT {_COLUMNS}
              FROM occurrences
              {where_sql}
          ORDER BY last_seen_at DESC, id
             LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).all()

    return OccurrenceListOut(
        items=[_row_to_out(r) for r in rows],
        page=page,
        page_size=page_size,
        total=int(total_row.n),
    )


@router.get(
    "/{occurrence_id}",
    response_model=OccurrenceOut,
    dependencies=[Depends(_ReadAccess)],
)
def get_occurrence(
    occurrence_id: UUID,
    db: Session = Depends(get_tenant_db),
) -> OccurrenceOut:
    return _fetch_occurrence(db, occurrence_id)


# ---------------------------------------------------------------------------
# Acknowledge
# ---------------------------------------------------------------------------


@router.post(
    "/{occurrence_id}/acknowledge",
    response_model=OccurrenceOut,
    summary="Marca a ocorrencia como reconhecida (open -> ack)",
)
def acknowledge_occurrence(
    request: Request,
    occurrence_id: UUID,
    db: Session = Depends(get_tenant_db),
    claims: AccessClaims = Depends(_WriteAccess),
) -> OccurrenceOut:
    current = _fetch_occurrence(db, occurrence_id)

    if current.status in _TERMINAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "ocorrencia ja esta em estado terminal "
                f"('{current.status}')"
            ),
        )

    if current.status == "ack":
        # Idempotente: re-acknowledge nao audita nem muda nada.
        return current

    row = db.execute(
        text(
            f"""
            UPDATE occurrences
               SET status = 'ack', updated_at = now()
             WHERE id = :oid
         RETURNING {_COLUMNS}
            """
        ),
        {"oid": str(occurrence_id)},
    ).one()

    _audit(
        db,
        actor_user_id=claims.sub,
        action="occurrence.acknowledge",
        resource_id=str(occurrence_id),
        request=request,
        metadata={
            "status_from": current.status,
            "status_to": "ack",
        },
    )

    logger.info(
        "occurrences.acknowledge.ok",
        extra={
            "tenant_id": str(claims.tid),
            "occurrence_id": str(occurrence_id),
            "status_from": current.status,
        },
    )
    return _row_to_out(row)


# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------


@router.post(
    "/{occurrence_id}/resolve",
    response_model=OccurrenceOut,
    summary="Marca a ocorrencia como resolvida (nota obrigatoria)",
)
def resolve_occurrence(
    request: Request,
    occurrence_id: UUID,
    payload: OccurrenceResolveIn,
    db: Session = Depends(get_tenant_db),
    claims: AccessClaims = Depends(_WriteAccess),
) -> OccurrenceOut:
    current = _fetch_occurrence(db, occurrence_id)

    if current.status == "ignored":
        # `resolved` ja resolvido e idempotente; `ignored` e outro estado
        # terminal e exige re-abrir antes de resolver.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ocorrencia ja foi marcada como ignored",
        )

    row = db.execute(
        text(
            f"""
            UPDATE occurrences
               SET status = 'resolved',
                   resolved_at = COALESCE(resolved_at, now()),
                   updated_at = now()
             WHERE id = :oid
         RETURNING {_COLUMNS}
            """
        ),
        {"oid": str(occurrence_id)},
    ).one()

    _audit(
        db,
        actor_user_id=claims.sub,
        action="occurrence.resolve",
        resource_id=str(occurrence_id),
        request=request,
        metadata={
            "status_from": current.status,
            "status_to": "resolved",
            "note": payload.note,
        },
    )

    logger.info(
        "occurrences.resolve.ok",
        extra={
            "tenant_id": str(claims.tid),
            "occurrence_id": str(occurrence_id),
            "status_from": current.status,
            # nota nao e segredo, mas mantemos so o tamanho no log para
            # nao poluir telemetria.
            "note_len": len(payload.note),
        },
    )
    return _row_to_out(row)


# ---------------------------------------------------------------------------
# Assign
# ---------------------------------------------------------------------------


def _assert_user_in_tenant(db: Session, user_id: UUID) -> None:
    """Confirma que o user e membro do tenant corrente.

    `tenant_users` tem RLS, entao a query naturalmente nao enxerga
    membros de outro tenant. 404 se nao for membro — mesma semantica
    do "nao existe na minha visao".
    """
    row = db.execute(
        text(
            """
            SELECT 1
              FROM tenant_users
             WHERE user_id = :uid
             LIMIT 1
            """
        ),
        {"uid": str(user_id)},
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="usuario nao e membro do tenant",
        )


@router.post(
    "/{occurrence_id}/assign",
    response_model=OccurrenceOut,
    summary="Atribui a ocorrencia a um membro do tenant",
)
def assign_occurrence(
    request: Request,
    occurrence_id: UUID,
    payload: OccurrenceAssignIn,
    db: Session = Depends(get_tenant_db),
    claims: AccessClaims = Depends(_WriteAccess),
) -> OccurrenceOut:
    current = _fetch_occurrence(db, occurrence_id)
    _assert_user_in_tenant(db, payload.assignee_user_id)

    row = db.execute(
        text(
            f"""
            UPDATE occurrences
               SET assignee_user_id = :aid, updated_at = now()
             WHERE id = :oid
         RETURNING {_COLUMNS}
            """
        ),
        {"aid": str(payload.assignee_user_id), "oid": str(occurrence_id)},
    ).one()

    _audit(
        db,
        actor_user_id=claims.sub,
        action="occurrence.assign",
        resource_id=str(occurrence_id),
        request=request,
        metadata={
            "assignee_user_id": str(payload.assignee_user_id),
            "previous_assignee_user_id": (
                str(current.assignee_user_id)
                if current.assignee_user_id is not None
                else None
            ),
        },
    )

    logger.info(
        "occurrences.assign.ok",
        extra={
            "tenant_id": str(claims.tid),
            "occurrence_id": str(occurrence_id),
            "assignee_user_id": str(payload.assignee_user_id),
        },
    )
    return _row_to_out(row)
