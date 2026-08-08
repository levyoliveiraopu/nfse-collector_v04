"""Seed de dev: plans + tenant demo + user admin (DATA-07).

Popula o ambiente de desenvolvimento com dados minimos para iniciar a API
e o painel web:

- Catalogo de plans `starter`, `pro` e `scale` (limites em `jsonb`).
- Tenant `demo` (slug `demo`, plan `pro`).
- User global `admin@demo.local` com senha vinda de `API_SEED_ADMIN_PASSWORD`.
- Membership `owner` ligando o user ao tenant.

**Idempotente**: todos os insercoes usam `ON CONFLICT ... DO UPDATE`, o que
significa que rodar o script N vezes deixa o banco no mesmo estado final
sem duplicar linhas nem estourar constraints.

Uso:

    # A partir de apps/api/
    API_DATABASE_URL=postgresql+psycopg://... \
    API_SEED_ADMIN_PASSWORD=demo12345 \
        python -m scripts.seed

Em `API_ENVIRONMENT=development` a senha tem um fallback `demo12345`
(com warning ruidoso). Em `staging`/`production` o script aborta se
`API_SEED_ADMIN_PASSWORD` nao estiver definida — evita criar
credenciais default em ambiente que vaza.

Observacoes:

- Usa `get_admin_session()` (BYPASSRLS) porque o seed cria o proprio
  tenant — nao ha GUC `app.current_tenant` para setar ainda.
- Nao insere linha em `subscriptions`. Billing esta adiado (ADR-004);
  o plano do tenant vive em `tenants.plan_id` por enquanto.
- `users` tem indice unico em `LOWER(email)`, entao o upsert usa
  `ON CONFLICT ((LOWER(email)))` (index predicate por expressao).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

# Imports do pacote da API. Quando rodado via `python -m scripts.seed`
# a partir de `apps/api/`, `api.*` e importavel porque `apps/api/` esta
# no sys.path (alembic.ini tambem depende disso).
from api.config import get_settings
from api.db import get_admin_session
from api.logging import configure_logging
from api.security.password import hash_password

log = logging.getLogger("nfse.seed")


# ---------------------------------------------------------------------------
# Dados do seed
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlanSpec:
    code: str
    name: str
    limits: dict[str, Any]
    price_cents: int


PLANS: tuple[PlanSpec, ...] = (
    PlanSpec(
        code="starter",
        name="Starter",
        limits={"companies": 1, "executions_per_month": 200, "users": 2},
        price_cents=0,
    ),
    PlanSpec(
        code="pro",
        name="Pro",
        limits={"companies": 5, "executions_per_month": 2000, "users": 5},
        price_cents=14900,
    ),
    PlanSpec(
        code="scale",
        name="Scale",
        limits={"companies": 25, "executions_per_month": 20000, "users": 15},
        price_cents=49900,
    ),
)

DEMO_TENANT_SLUG = "demo"
DEMO_TENANT_NAME = "Tenant Demo"
DEMO_TENANT_PLAN = "pro"

DEMO_USER_EMAIL = "admin@demo.local"
DEMO_USER_NAME = "Admin Demo"
DEMO_USER_ROLE = "owner"

# Senha default usada apenas em `API_ENVIRONMENT=development` quando
# `API_SEED_ADMIN_PASSWORD` nao e fornecida. Fora de dev o script aborta.
_DEV_FALLBACK_PASSWORD = "demo12345"


# ---------------------------------------------------------------------------
# Upserts
# ---------------------------------------------------------------------------

def upsert_plan(session: Session, plan: PlanSpec) -> None:
    """Insere/atualiza um plano por `code` (PK).

    `limits` vai como JSONB. `active` e preservado em true (default do schema).
    """
    session.execute(
        text(
            """
            INSERT INTO plans (code, name, limits, price_cents, active)
            VALUES (:code, :name, CAST(:limits AS jsonb), :price_cents, true)
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                limits = EXCLUDED.limits,
                price_cents = EXCLUDED.price_cents,
                active = true,
                updated_at = now()
            """
        ),
        {
            "code": plan.code,
            "name": plan.name,
            "limits": json.dumps(plan.limits),
            "price_cents": plan.price_cents,
        },
    )
    log.info(
        "seed.plan.upserted",
        extra={"code": plan.code, "price_cents": plan.price_cents},
    )


def upsert_tenant(
    session: Session,
    *,
    slug: str,
    name: str,
    plan_id: str,
) -> UUID:
    """Insere/atualiza tenant por `slug` (unique). Retorna o `id`."""
    row = session.execute(
        text(
            """
            INSERT INTO tenants (name, slug, plan_id, status)
            VALUES (:name, :slug, :plan_id, 'active')
            ON CONFLICT (slug) DO UPDATE SET
                name = EXCLUDED.name,
                plan_id = EXCLUDED.plan_id,
                status = 'active',
                updated_at = now()
            RETURNING id
            """
        ),
        {"name": name, "slug": slug, "plan_id": plan_id},
    ).one()
    tenant_id: UUID = row[0]
    log.info(
        "seed.tenant.upserted",
        extra={"slug": slug, "tenant_id": str(tenant_id)},
    )
    return tenant_id


def upsert_user(
    session: Session,
    *,
    email: str,
    name: str,
    password_hash: str,
) -> UUID:
    """Insere/atualiza user global por `LOWER(email)`. Retorna o `id`.

    `users` tem indice unico em `LOWER(email)` (nao em `email`). O
    Postgres aceita `ON CONFLICT` referenciando a expressao indexada.
    """
    row = session.execute(
        text(
            """
            INSERT INTO users (email, name, password_hash, status)
            VALUES (:email, :name, :password_hash, 'active')
            ON CONFLICT ((LOWER(email))) DO UPDATE SET
                name = EXCLUDED.name,
                password_hash = EXCLUDED.password_hash,
                status = 'active',
                updated_at = now()
            RETURNING id
            """
        ),
        {"email": email, "name": name, "password_hash": password_hash},
    ).one()
    user_id: UUID = row[0]
    log.info(
        "seed.user.upserted",
        extra={"email": email, "user_id": str(user_id)},
    )
    return user_id


def upsert_membership(
    session: Session,
    *,
    tenant_id: UUID,
    user_id: UUID,
    role: str,
) -> None:
    """Insere/atualiza membership (PK composta `(tenant_id, user_id)`).

    `tenant_users` tem RLS forcada. Como esta sessao e `app_admin`
    (BYPASSRLS), a escrita passa pela policy.
    """
    session.execute(
        text(
            """
            INSERT INTO tenant_users (tenant_id, user_id, role, accepted_at)
            VALUES (:tenant_id, :user_id, :role, now())
            ON CONFLICT (tenant_id, user_id) DO UPDATE SET
                role = EXCLUDED.role,
                accepted_at = COALESCE(tenant_users.accepted_at, now())
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "role": role,
        },
    )
    log.info(
        "seed.membership.upserted",
        extra={
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "role": role,
        },
    )


# ---------------------------------------------------------------------------
# Orquestracao
# ---------------------------------------------------------------------------

def resolve_admin_password() -> str:
    """Le `API_SEED_ADMIN_PASSWORD`; em dev cai para fallback com warning."""
    pwd = os.environ.get("API_SEED_ADMIN_PASSWORD", "").strip()
    if pwd:
        return pwd

    settings = get_settings()
    if settings.environment != "development":
        raise SystemExit(
            "API_SEED_ADMIN_PASSWORD nao definida. Este script so aceita "
            "fallback default em API_ENVIRONMENT=development."
        )

    log.warning(
        "API_SEED_ADMIN_PASSWORD ausente; usando senha default de dev. "
        "NAO USE EM STAGING/PRODUCAO.",
        extra={"event": "seed.admin_password.fallback"},
    )
    return _DEV_FALLBACK_PASSWORD


def resolve_tenant_name() -> str:
    """Mantem o slug demo e permite personalizar apenas o nome exibido."""
    return os.environ.get("API_SEED_TENANT_NAME", "").strip() or DEMO_TENANT_NAME


def run_seed() -> None:
    """Aplica o seed numa unica transacao (commit no `with` do context manager)."""
    admin_password = resolve_admin_password()
    password_hash = hash_password(admin_password)

    with get_admin_session() as session:
        for plan in PLANS:
            upsert_plan(session, plan)

        tenant_id = upsert_tenant(
            session,
            slug=DEMO_TENANT_SLUG,
            name=resolve_tenant_name(),
            plan_id=DEMO_TENANT_PLAN,
        )

        user_id = upsert_user(
            session,
            email=DEMO_USER_EMAIL,
            name=DEMO_USER_NAME,
            password_hash=password_hash,
        )

        upsert_membership(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            role=DEMO_USER_ROLE,
        )

    log.info(
        "seed.completed",
        extra={
            "plans": [p.code for p in PLANS],
            "tenant_slug": DEMO_TENANT_SLUG,
            "user_email": DEMO_USER_EMAIL,
        },
    )


def main() -> int:
    configure_logging()
    try:
        run_seed()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        log.error("seed.failed", extra={"error": str(exc)})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
