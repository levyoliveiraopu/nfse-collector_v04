"""companies: deleted_at para soft delete (API-05)

Revision ID: 0015_companies_deleted_at
Revises: 0014_plans_subscriptions
Create Date: 2026-04-14

Entregavel acoplado ao ticket API-05 (CRUD de `/companies`).

Motivacao:
- DATA-02 criou `companies.status IN ('active','paused','disabled')` com
  semantica operacional. `disabled` nao serve como marcador de remocao:
  e um estado reversivel (tenant pode reativar) e impede distinguir
  "company desativada mas ainda visivel" de "company removida".
- API-05 exige `DELETE /companies/{id} (soft delete)`. Para manter o
  endpoint idempotente e permitir re-registro do mesmo CNPJ apos delete
  (cenario comum em contabilidades que perdem e recuperam clientes),
  adicionamos `deleted_at TIMESTAMPTZ NULL` e tornamos a unicidade de
  CNPJ parcial (apenas entre linhas nao-deletadas).

Mudancas:
1. `companies.deleted_at TIMESTAMPTZ NULL`.
2. `uq_companies_tenant_cnpj` (UNIQUE total) -> UNIQUE parcial
   `WHERE deleted_at IS NULL`. Dois CNPJs iguais so coexistem se no
   maximo um estiver "vivo".
3. Indice parcial `ix_companies_tenant_live` em `(tenant_id)` com
   `WHERE deleted_at IS NULL` para listagens do handler `GET /companies`.

Compatibilidade:
- `UNIQUE(tenant_id, id)` (usado como FK composta por
  `company_credentials`) permanece intacto — remocoes sao por soft-delete,
  entao `id` continua estavel.
- RLS existente (policy `companies_isolation`) e preservada.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015_companies_deleted_at"
down_revision: Union[str, None] = "0014_plans_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Nova coluna deleted_at.
    op.add_column(
        "companies",
        sa.Column(
            "deleted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )

    # 2. Substituir UNIQUE(tenant_id, cnpj) por UNIQUE parcial.
    #    Precisa ser um INDEX UNIQUE parcial (Postgres nao aceita WHERE em
    #    UNIQUE CONSTRAINT). Removemos a constraint antes de criar o indice.
    op.drop_constraint(
        "uq_companies_tenant_cnpj",
        "companies",
        type_="unique",
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_companies_tenant_cnpj_live
            ON companies (tenant_id, cnpj)
         WHERE deleted_at IS NULL
        """
    )

    # 3. Indice parcial para listagens "vivas" (GET /companies).
    op.execute(
        """
        CREATE INDEX ix_companies_tenant_live
            ON companies (tenant_id, created_at DESC)
         WHERE deleted_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_companies_tenant_live")
    op.execute("DROP INDEX IF EXISTS uq_companies_tenant_cnpj_live")

    # Recria o UNIQUE total. Pode falhar se houver linhas duplicadas por
    # cnpj; downgrade e operacao manual em staging.
    op.create_unique_constraint(
        "uq_companies_tenant_cnpj",
        "companies",
        ["tenant_id", "cnpj"],
    )

    op.drop_column("companies", "deleted_at")
