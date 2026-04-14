"""reprocess_jobs: jobs de reprocessamento em lote (+ RLS)

Revision ID: 0007_reprocess_jobs
Revises: 0006_occurrences
Create Date: 2026-04-14

Entregavel do ticket DATA-04 (parte 2/3):
- Tabela `reprocess_jobs` para enfileirar pedidos de reprocessamento
  disparados do painel (ex.: "rodar novamente as NFS-e de abril de
  todas as companies do tenant" ou "reprocessar execution_items em
  `failed`"). O worker consumira o job e preenchera
  `result_execution_ids` com as execucoes geradas — as execucoes
  propriamente vivem em `executions` (DATA-03).
- `scope` e JSONB livre nesta fase (shape canonico sera decidido pelos
  tickets de API/worker que consumirem o job, ex.:
  `{"kind":"period","company_ids":[...],"period_start":"...",
  "period_end":"..."}` ou
  `{"kind":"execution_items","item_ids":[...]}`).
- `result_execution_ids text[]` conforme o ticket (note: text, nao
  uuid[]; mantemos como definido no backlog e deixamos o cast para a
  camada de aplicacao).
- `created_by_user_id -> users(id)` nullable com `ON DELETE SET NULL`
  (preserva o historico mesmo se o user for removido; `users` e
  global, sem `tenant_id`).
- RLS ativada via GUC `app.current_tenant`.

Observacoes:
- `status` com CHECK (`queued`, `running`, `succeeded`, `failed`,
  `cancelled`).
- Indice `(tenant_id, status)` acelera "jobs ativos deste tenant".
- Indice `(tenant_id, created_at DESC)` acelera a listagem do painel.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_reprocess_jobs"
down_revision: Union[str, None] = "0006_occurrences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


REPROCESS_JOB_STATUS = (
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
)


def upgrade() -> None:
    # -------------------------------------------------------------------
    # 1. reprocess_jobs
    # -------------------------------------------------------------------
    op.create_table(
        "reprocess_jobs",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "scope",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column(
            "result_execution_ids",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')",
            name="ck_reprocess_jobs_status",
        ),
    )

    op.create_index(
        "ix_reprocess_jobs_tenant_id",
        "reprocess_jobs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_reprocess_jobs_tenant_status",
        "reprocess_jobs",
        ["tenant_id", "status"],
    )
    # Listagem cronologica no painel ("jobs recentes deste tenant").
    op.create_index(
        "ix_reprocess_jobs_tenant_created",
        "reprocess_jobs",
        ["tenant_id", sa.text("created_at DESC")],
    )

    # -------------------------------------------------------------------
    # 2. Grants para app_user.
    # -------------------------------------------------------------------
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON reprocess_jobs TO app_user"
    )

    # -------------------------------------------------------------------
    # 3. RLS.
    # -------------------------------------------------------------------
    op.execute("ALTER TABLE reprocess_jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE reprocess_jobs FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY reprocess_jobs_isolation ON reprocess_jobs
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS reprocess_jobs_isolation ON reprocess_jobs"
    )
    op.execute(
        "ALTER TABLE IF EXISTS reprocess_jobs DISABLE ROW LEVEL SECURITY"
    )

    op.drop_index("ix_reprocess_jobs_tenant_created", table_name="reprocess_jobs")
    op.drop_index("ix_reprocess_jobs_tenant_status", table_name="reprocess_jobs")
    op.drop_index("ix_reprocess_jobs_tenant_id", table_name="reprocess_jobs")
    op.drop_table("reprocess_jobs")
