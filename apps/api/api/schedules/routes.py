"""Endpoints de `/schedules` (API-12).

CRUD de agendamentos de execucao automatica por tenant, com validacao
de cron + timezone e calculo de `next_run_at` a cada criacao/edicao que
afete o tempo (cron, tz ou reativacao via `enabled=true`).

Isolamento: `get_tenant_db` (API-03) ja aplica RLS via GUC; a policy
`schedules_isolation` + a FK composta `(tenant_id, company_id)` da
migration 0012 garantem que uma agenda nao possa vincular company de
outro tenant mesmo se a camada de app falhar.

RBAC (matriz em `docs/architecture/rbac-matrix.md`):

- `GET /schedules`, `GET /schedules/{id}`, `GET /schedules/presets`:
  todos (min_role=viewer).
- `POST`, `PATCH`: owner | admin | operator.
- `DELETE`: owner | admin.

Observacoes de design:

- `cron_expr` e `timezone` invalidos viram **400** (mesmo quando
  detectados no Pydantic — o router intercepta `RequestValidationError`?
  Nao: Pydantic -> 422. Para cumprir o DoD ("cron invalido retorna 400
  claro"), o router tambem valida explicitamente antes do insert e
  levanta `HTTPException(400)`. O schema valida primeiro e devolve 422
  apenas se o cliente passar `extra` ou tipo errado; cron malformado
  cai no bloco explicito do handler -> 400.
- `last_run_at` e read-only via API; apenas o worker atualiza. O schema
  `ScheduleUpdate` ja rejeita a chave via `extra=forbid` -> 422.
- Company opcional: Null = agenda "do tenant inteiro". Quando informada,
  validamos que a company existe (e nao esta soft-deleted) no tenant
  corrente — via SELECT em `companies` protegida por RLS. Company
  inexistente/soft-deleted -> 400 (nao 404, pois o recurso sendo criado
  nao e a company).
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..deps import get_tenant_db
from ..security.jwt import AccessClaims
from ..security.rbac import require_role
from .cron import (
    CronValidationError,
    compute_next_run,
    validate_cron,
    validate_timezone,
)
from .presets import PRESETS
from .schemas import (
    ScheduleIn,
    ScheduleListOut,
    ScheduleOut,
    SchedulePresetListOut,
    SchedulePresetOut,
    ScheduleUpdate,
)

logger = logging.getLogger("api.schedules")

router = APIRouter(prefix="/schedules", tags=["schedules"])

_ReadAccess = require_role("owner", "admin", "operator", "viewer")
_WriteAccess = require_role("owner", "admin", "operator")
_DeleteAccess = require_role("owner", "admin")

_COLUMNS = (
    "id, tenant_id, company_id, cron_expr, timezone, enabled, "
    "last_run_at, next_run_at, created_by_user_id, created_at, updated_at"
)


def _row_to_out(row) -> ScheduleOut:
    return ScheduleOut(
        id=row.id,
        tenant_id=row.tenant_id,
        company_id=row.company_id,
        cron_expr=row.cron_expr,
        timezone=row.timezone,
        enabled=row.enabled,
        last_run_at=row.last_run_at,
        next_run_at=row.next_run_at,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _assert_company_exists(db: Session, company_id: UUID) -> None:
    """Garante que a company existe e nao esta soft-deleted no tenant corrente.

    Usa a sessao tenant-db (RLS ativa), portanto so enxerga companies
    do proprio tenant. Qualquer outro cenario -> 400.
    """
    row = db.execute(
        text(
            """
            SELECT 1 FROM companies
             WHERE id = :cid AND deleted_at IS NULL
             LIMIT 1
            """
        ),
        {"cid": str(company_id)},
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="company_id nao encontrado ou soft-deleted",
        )


def _safe_compute_next_run(cron_expr: str, tz: str) -> str:
    """Wrapper que mapeia erros de cron/tz para 400."""
    try:
        return compute_next_run(cron_expr, tz).isoformat()
    except CronValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Presets (read-only)
# ---------------------------------------------------------------------------


@router.get(
    "/presets",
    response_model=SchedulePresetListOut,
    dependencies=[Depends(_ReadAccess)],
)
def list_presets() -> SchedulePresetListOut:
    return SchedulePresetListOut(
        items=[SchedulePresetOut(**p) for p in PRESETS],
    )


# ---------------------------------------------------------------------------
# List / detail
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=ScheduleListOut,
    dependencies=[Depends(_ReadAccess)],
)
def list_schedules(
    db: Session = Depends(get_tenant_db),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
    enabled: Optional[bool] = Query(default=None),
    company_id: Optional[UUID] = Query(default=None),
) -> ScheduleListOut:
    params: dict[str, object] = {
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    where: list[str] = []
    if enabled is not None:
        where.append("enabled = :enabled")
        params["enabled"] = enabled
    if company_id is not None:
        where.append("company_id = :company_id")
        params["company_id"] = str(company_id)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    total_row = db.execute(
        text(f"SELECT COUNT(*) AS n FROM schedules{where_sql}"),
        params,
    ).one()

    rows = db.execute(
        text(
            f"""
            SELECT {_COLUMNS}
              FROM schedules{where_sql}
          ORDER BY created_at DESC, id
             LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).all()

    return ScheduleListOut(
        items=[_row_to_out(r) for r in rows],
        page=page,
        page_size=page_size,
        total=int(total_row.n),
    )


@router.get(
    "/{schedule_id}",
    response_model=ScheduleOut,
    dependencies=[Depends(_ReadAccess)],
)
def get_schedule(
    schedule_id: UUID,
    db: Session = Depends(get_tenant_db),
) -> ScheduleOut:
    row = db.execute(
        text(f"SELECT {_COLUMNS} FROM schedules WHERE id = :sid"),
        {"sid": str(schedule_id)},
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="schedule nao encontrado",
        )
    return _row_to_out(row)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ScheduleOut,
    status_code=status.HTTP_201_CREATED,
)
def create_schedule(
    payload: ScheduleIn,
    db: Session = Depends(get_tenant_db),
    claims: AccessClaims = Depends(_WriteAccess),
) -> ScheduleOut:
    # Defesa em profundidade: re-validar cron/tz para o DoD "cron invalido
    # -> 400". O schema ja rejeitou antes (422), mas em fluxos futuros
    # (ex.: recomputar via outro endpoint) o handler e a fonte de verdade.
    try:
        cron_expr = validate_cron(payload.cron_expr)
        tz = validate_timezone(payload.timezone)
    except CronValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if payload.company_id is not None:
        _assert_company_exists(db, payload.company_id)

    next_run_iso = _safe_compute_next_run(cron_expr, tz) if payload.enabled else None

    params = {
        "tid": str(claims.tid),
        "company_id": str(payload.company_id) if payload.company_id else None,
        "cron_expr": cron_expr,
        "timezone": tz,
        "enabled": payload.enabled,
        "next_run_at": next_run_iso,
        "created_by": str(claims.sub),
    }
    try:
        row = db.execute(
            text(
                f"""
                INSERT INTO schedules (
                    tenant_id, company_id, cron_expr, timezone,
                    enabled, next_run_at, created_by_user_id
                ) VALUES (
                    :tid, :company_id, :cron_expr, :timezone,
                    :enabled, :next_run_at, :created_by
                )
                RETURNING {_COLUMNS}
                """
            ),
            params,
        ).one()
    except IntegrityError as exc:
        # FK composta `(tenant_id, company_id) -> companies`: caso a
        # company some entre o SELECT e o INSERT (corrida improvavel),
        # devolvemos 400 coerente com a mensagem anterior.
        logger.info(
            "schedules.create.integrity",
            extra={"tenant_id": str(claims.tid), "error": str(exc.orig)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="company_id invalido para o tenant",
        ) from exc

    logger.info(
        "schedules.create.ok",
        extra={
            "tenant_id": str(claims.tid),
            "schedule_id": str(row.id),
            "cron_expr": cron_expr,
            "timezone": tz,
            "enabled": payload.enabled,
            "has_company": payload.company_id is not None,
        },
    )
    return _row_to_out(row)


# ---------------------------------------------------------------------------
# Update (pause/resume + edicao parcial)
# ---------------------------------------------------------------------------


@router.patch(
    "/{schedule_id}",
    response_model=ScheduleOut,
    dependencies=[Depends(_WriteAccess)],
)
def update_schedule(
    schedule_id: UUID,
    payload: ScheduleUpdate,
    db: Session = Depends(get_tenant_db),
) -> ScheduleOut:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payload vazio",
        )

    # Carrega o estado atual para decidir quando recalcular `next_run_at`.
    current = db.execute(
        text(f"SELECT {_COLUMNS} FROM schedules WHERE id = :sid"),
        {"sid": str(schedule_id)},
    ).one_or_none()
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="schedule nao encontrado",
        )

    # Se o payload incluir explicitamente uma nova company_id, valida.
    # Valor `None` explicito e permitido e vira NULL (agenda tenant-wide).
    if "company_id" in updates and updates["company_id"] is not None:
        _assert_company_exists(db, updates["company_id"])

    # Valores efetivos apos a edicao, usados para recalcular next_run_at.
    next_cron = updates.get("cron_expr", current.cron_expr)
    next_tz = updates.get("timezone", current.timezone)
    next_enabled = updates.get("enabled", current.enabled)

    cron_changed = "cron_expr" in updates and updates["cron_expr"] != current.cron_expr
    tz_changed = "timezone" in updates and updates["timezone"] != current.timezone
    enabled_flip_to_true = (
        "enabled" in updates and updates["enabled"] is True and not current.enabled
    )
    enabled_flip_to_false = (
        "enabled" in updates and updates["enabled"] is False and current.enabled
    )

    recompute_next = cron_changed or tz_changed or enabled_flip_to_true
    clear_next = enabled_flip_to_false and not recompute_next

    if recompute_next and next_enabled:
        updates["next_run_at"] = _safe_compute_next_run(next_cron, next_tz)
    elif recompute_next and not next_enabled:
        # cron/tz mudou mas ficou desabilitada -> limpa o ponteiro.
        updates["next_run_at"] = None
    elif clear_next:
        updates["next_run_at"] = None

    # Normaliza string do UUID para o bind (SQLAlchemy aceita UUID, mas
    # usamos str por consistencia com o resto do router).
    if "company_id" in updates and updates["company_id"] is not None:
        updates["company_id"] = str(updates["company_id"])

    set_fragments = [f"{k} = :{k}" for k in updates]
    set_fragments.append("updated_at = now()")
    set_sql = ", ".join(set_fragments)

    params: dict[str, object] = dict(updates)
    params["sid"] = str(schedule_id)

    try:
        row = db.execute(
            text(
                f"""
                UPDATE schedules
                   SET {set_sql}
                 WHERE id = :sid
             RETURNING {_COLUMNS}
                """
            ),
            params,
        ).one_or_none()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="company_id invalido para o tenant",
        ) from exc

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="schedule nao encontrado",
        )
    return _row_to_out(row)


# ---------------------------------------------------------------------------
# Delete (hard)
# ---------------------------------------------------------------------------


@router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_DeleteAccess)],
)
def delete_schedule(
    schedule_id: UUID,
    db: Session = Depends(get_tenant_db),
) -> Response:
    row = db.execute(
        text("DELETE FROM schedules WHERE id = :sid RETURNING id"),
        {"sid": str(schedule_id)},
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="schedule nao encontrado",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
