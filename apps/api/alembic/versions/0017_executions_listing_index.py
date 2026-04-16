"""executions: indices auxiliares para listagem (API-08)

Revision ID: 0017_executions_listing_index
Revises: 0016_merge_0015_heads
Create Date: 2026-04-16

Entregavel do ticket API-08 (Definition of Done: "Query valida com
EXPLAIN (usa indice)"). Adiciona dois indices em `executions` que
cobrem as queries dos novos endpoints `GET /executions` e
`GET /companies/{id}/executions`:

1. `ix_executions_tenant_started` em `(tenant_id, started_at DESC NULLS
   LAST, id)`. Cobre `WHERE tenant_id = :t ORDER BY started_at DESC
   NULLS LAST, id LIMIT N` — a query padrao do `GET /executions` sem
   filtro por company. O `NULLS LAST` casa com a sintaxe da query e
   evita um sort adicional para execucoes ainda em `queued` (sem
   `started_at`).

2. `ix_executions_tenant_status_started` em
   `(tenant_id, status, started_at DESC NULLS LAST)`. Cobre o filtro
   `?status=` que e comum no painel (ex.: ver so as `failed`).

Indices ja existentes em `0004_executions.py` continuam servindo:
- `ix_executions_tenant_company_started` (tenant_id, company_id,
  started_at DESC) — usado quando `company_id` esta presente na query
  (atalho `/companies/{id}/executions` ou `?company_id=` no listador).
- `ix_executions_tenant_id` — fallback para counts amplos.

Para `execution_items` o indice `ix_execution_items_execution_id` ja
cobre as listagens por execution; nao adicionamos indice por status/nsu
porque a cardinalidade dentro de uma execucao e baixa o suficiente
para um Bitmap Heap Scan apos o filtro de execution_id ser barato.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017_executions_listing_index"
down_revision: Union[str, None] = "0016_merge_0015_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_executions_tenant_started",
        "executions",
        ["tenant_id", sa.text("started_at DESC NULLS LAST"), "id"],
    )
    op.create_index(
        "ix_executions_tenant_status_started",
        "executions",
        ["tenant_id", "status", sa.text("started_at DESC NULLS LAST")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_executions_tenant_status_started", table_name="executions"
    )
    op.drop_index("ix_executions_tenant_started", table_name="executions")
