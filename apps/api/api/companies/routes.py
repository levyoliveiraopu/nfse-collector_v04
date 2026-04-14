"""Endpoints de `/companies` (API-05).

CRUD de CNPJs por tenant. Protegido por:

- `get_tenant_db` (API-03) — RLS setada via GUC, isolamento cross-tenant
  garantido pelas policies `companies_isolation` e pelo CHECK de tenant
  no WHERE de todos os comandos.
- `require_role` (API-04) — papeis permitidos seguem a matriz em
  `docs/architecture/rbac-matrix.md`:
    * GET (lista/detalhe)     : todos (min_role=viewer)
    * POST / PATCH            : owner, admin, operator
    * DELETE (soft)           : owner, admin

Soft delete: grava `deleted_at = now()` (coluna adicionada em
`0015_companies_deleted_at`). Listagens e buscas filtram
`WHERE deleted_at IS NULL`.

Limite de plano: no POST, consulta `tenants.plan_id -> plans.limits ->>
'max_companies'`. Se a chave existir e a contagem de companies vivas do
tenant ja atingiu o teto, devolve 409 — alinhado com ADR-004 (billing
adiado, mas limite ja aplicavel).
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
from .schemas import (
    CompanyIn,
    CompanyListOut,
    CompanyOut,
    CompanyStatus,
    CompanyUpdate,
)

logger = logging.getLogger("api.companies")

router = APIRouter(prefix="/companies", tags=["companies"])

# Dependencies RBAC — factory calls intencionalmente a nivel de modulo
# para que o OpenAPI liste os papeis via `include_in_schema`.
_ReadAccess = require_role("owner", "admin", "operator", "viewer")
_WriteAccess = require_role("owner", "admin", "operator")
_DeleteAccess = require_role("owner", "admin")


def _resolve_company_cap(db: Session) -> Optional[int]:
    """Retorna o limite de companies do plano do tenant, ou None.

    Le `tenants.plan_id -> plans.limits->>'max_companies'`. Como `plans`
    nao tem RLS e `tenants` e visivel via policy do tenant corrente, a
    query roda direto na sessao tenant-db.
    """
    row = db.execute(
        text(
            """
            SELECT (p.limits ->> 'max_companies')::int AS cap
              FROM tenants t
              LEFT JOIN plans p ON p.code = t.plan_id
             WHERE t.id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
            """
        )
    ).one_or_none()
    if row is None or row.cap is None:
        return None
    return int(row.cap)


def _count_live_companies(db: Session) -> int:
    row = db.execute(
        text(
            """
            SELECT COUNT(*) AS n FROM companies
             WHERE deleted_at IS NULL
            """
        )
    ).one()
    return int(row.n)


def _row_to_out(row) -> CompanyOut:
    return CompanyOut(
        id=row.id,
        tenant_id=row.tenant_id,
        cnpj=row.cnpj,
        razao_social=row.razao_social,
        nome_fantasia=row.nome_fantasia,
        municipio_ibge=row.municipio_ibge,
        uf=row.uf,
        status=row.status,
        last_nsu=row.last_nsu,
        last_success_at=row.last_success_at,
        portal_provider=row.portal_provider,
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


_COLUMNS = (
    "id, tenant_id, cnpj, razao_social, nome_fantasia, municipio_ibge, "
    "uf, status, last_nsu, last_success_at, portal_provider, notes, "
    "created_at, updated_at"
)


@router.get(
    "",
    response_model=CompanyListOut,
    dependencies=[Depends(_ReadAccess)],
)
def list_companies(
    db: Session = Depends(get_tenant_db),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
    status_: Optional[CompanyStatus] = Query(default=None, alias="status"),
    uf: Optional[str] = Query(default=None, min_length=2, max_length=2),
) -> CompanyListOut:
    params: dict[str, object] = {
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    where = ["deleted_at IS NULL"]
    if status_ is not None:
        where.append("status = :status")
        params["status"] = status_
    if uf is not None:
        where.append("uf = :uf")
        params["uf"] = uf.upper()
    where_sql = " AND ".join(where)

    total_row = db.execute(
        text(f"SELECT COUNT(*) AS n FROM companies WHERE {where_sql}"),
        params,
    ).one()

    rows = db.execute(
        text(
            f"""
            SELECT {_COLUMNS}
              FROM companies
             WHERE {where_sql}
          ORDER BY created_at DESC, id
             LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).all()

    return CompanyListOut(
        items=[_row_to_out(r) for r in rows],
        page=page,
        page_size=page_size,
        total=int(total_row.n),
    )


@router.get(
    "/{company_id}",
    response_model=CompanyOut,
    dependencies=[Depends(_ReadAccess)],
)
def get_company(
    company_id: UUID,
    db: Session = Depends(get_tenant_db),
) -> CompanyOut:
    row = db.execute(
        text(
            f"""
            SELECT {_COLUMNS}
              FROM companies
             WHERE id = :cid AND deleted_at IS NULL
            """
        ),
        {"cid": str(company_id)},
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="company nao encontrada")
    return _row_to_out(row)


@router.post(
    "",
    response_model=CompanyOut,
    status_code=status.HTTP_201_CREATED,
)
def create_company(
    payload: CompanyIn,
    db: Session = Depends(get_tenant_db),
    claims: AccessClaims = Depends(_WriteAccess),
) -> CompanyOut:
    # Limite do plano (ADR-004): se `plans.limits->>'max_companies'` for
    # definido, recusamos criar alem do teto. Sem plano/sem chave: ilimitado.
    cap = _resolve_company_cap(db)
    if cap is not None:
        current = _count_live_companies(db)
        if current >= cap:
            logger.info(
                "companies.create.plan_limit",
                extra={
                    "tenant_id": str(claims.tid),
                    "cap": cap,
                    "current": current,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="limite de companies do plano atingido",
            )

    params = {
        "tid": str(claims.tid),
        "cnpj": payload.cnpj,
        "razao_social": payload.razao_social,
        "nome_fantasia": payload.nome_fantasia,
        "municipio_ibge": payload.municipio_ibge,
        "uf": payload.uf,
        "status": payload.status,
        "portal_provider": payload.portal_provider,
        "notes": payload.notes,
    }
    try:
        row = db.execute(
            text(
                f"""
                INSERT INTO companies (
                    tenant_id, cnpj, razao_social, nome_fantasia,
                    municipio_ibge, uf, status, portal_provider, notes
                ) VALUES (
                    :tid, :cnpj, :razao_social, :nome_fantasia,
                    :municipio_ibge, :uf, :status, :portal_provider, :notes
                )
                RETURNING {_COLUMNS}
                """
            ),
            params,
        ).one()
    except IntegrityError as exc:
        # UNIQUE parcial (tenant_id, cnpj) WHERE deleted_at IS NULL.
        logger.info("companies.create.conflict", extra={"tenant_id": str(claims.tid)})
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ja existe company ativa com este CNPJ",
        ) from exc

    return _row_to_out(row)


@router.patch(
    "/{company_id}",
    response_model=CompanyOut,
    dependencies=[Depends(_WriteAccess)],
)
def update_company(
    company_id: UUID,
    payload: CompanyUpdate,
    db: Session = Depends(get_tenant_db),
) -> CompanyOut:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payload vazio",
        )

    set_fragments = [f"{k} = :{k}" for k in updates]
    set_fragments.append("updated_at = now()")
    set_sql = ", ".join(set_fragments)

    params: dict[str, object] = dict(updates)
    params["cid"] = str(company_id)

    row = db.execute(
        text(
            f"""
            UPDATE companies
               SET {set_sql}
             WHERE id = :cid AND deleted_at IS NULL
         RETURNING {_COLUMNS}
            """
        ),
        params,
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="company nao encontrada",
        )
    return _row_to_out(row)


@router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_DeleteAccess)],
)
def soft_delete_company(
    company_id: UUID,
    db: Session = Depends(get_tenant_db),
) -> Response:
    row = db.execute(
        text(
            """
            UPDATE companies
               SET deleted_at = now(),
                   updated_at = now()
             WHERE id = :cid AND deleted_at IS NULL
         RETURNING id
            """
        ),
        {"cid": str(company_id)},
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="company nao encontrada",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
