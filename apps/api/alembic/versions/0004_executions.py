"""executions: uma execucao de coleta por (tenant, company) (+ RLS)

Revision ID: 0004_executions
Revises: 0003_company_credentials
Create Date: 2026-04-14

Entregavel do ticket DATA-03 (parte 1/2):
- Tabela `executions` com status da corrida, janela de periodo, range
  de NSU coberto e contagens agregadas (`items_total`/`items_ok`/
  `items_fail`).
- FK composta `(tenant_id, company_id) -> companies(tenant_id, id)`
  como defesa em profundidade (garante, no banco, que uma execucao
  nao pode referenciar uma company de outro tenant — mesmo padrao
  adotado em `company_credentials`).
- UNIQUE(tenant_id, id) habilita FK composta em `execution_items`.
- Indice composto `(tenant_id, company_id, started_at DESC)` para a
  query de listagem por periodo (DoD: EXPLAIN verde).
- RLS ativada via GUC `app.current_tenant` (mesmo padrao do DATA-01).

Observacoes:
- `trigger` e TEXT com CHECK (`manual`, `schedule`, `api`, `reprocess`).
- `status` e TEXT com CHECK (`queued`, `running`, `succeeded`, `failed`,
  `cancelled`, `partial`). `partial` cobre o caso de itens em falha
  parcial — nao forca "all-or-nothing".
- `triggered_by_user_id` e nullable (execucoes por cron/API podem nao
  ter usuario) e usa `ON DELETE SET NULL` para preservar o historico
  mesmo se o user for removido.
- `period_start`/`period_end` sao DATE (janela de competencia de NFS-e).
- `nsu_from`/`nsu_to` sao BIGINT (NSU de alguns portais cresce rapido).
- CHECK `period_end >= period_start` e CHECK
  `items_total >= items_ok + items_fail` defendem invariantes de dominio.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_executions"
down_revision: Union[str, None] = "0003_company_credentials"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EXECUTION_TRIGGER = ("manual", "schedule", "api", "reprocess")
EXECUTION_STATUS = (
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "partial",
)


def upgrade() -> None:
    # -------------------------------------------------------------------
    # 1. executions
    # -------------------------------------------------------------------
    op.create_table(
        "executions",
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
            "company_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column(
            "triggered_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("nsu_from", sa.BigInteger(), nullable=True),
        sa.Column("nsu_to", sa.BigInteger(), nullable=True),
        sa.Column(
            "items_total",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "items_ok",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "items_fail",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
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
        # FK composta: garante que company_id pertence ao mesmo tenant.
        sa.ForeignKeyConstraint(
            ["tenant_id", "company_id"],
            ["companies.tenant_id", "companies.id"],
            name="fk_executions_tenant_company",
            ondelete="CASCADE",
        ),
        # UNIQUE(tenant_id, id) habilita FK composta em execution_items.
        sa.UniqueConstraint("tenant_id", "id", name="uq_executions_tenant_id_id"),
        sa.CheckConstraint(
            "trigger IN ('manual','schedule','api','reprocess')",
            name="ck_executions_trigger",
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled','partial')",
            name="ck_executions_status",
        ),
        sa.CheckConstraint(
            "period_end >= period_start",
            name="ck_executions_period_order",
        ),
        sa.CheckConstraint(
            "items_total >= items_ok + items_fail",
            name="ck_executions_items_sum",
        ),
        sa.CheckConstraint(
            "items_total >= 0 AND items_ok >= 0 AND items_fail >= 0",
            name="ck_executions_items_non_negative",
        ),
    )

    op.create_index(
        "ix_executions_tenant_id",
        "executions",
        ["tenant_id"],
    )
    # Indice composto exigido pelo ticket (listagem por periodo mais recente
    # de um CNPJ dentro do tenant). started_at DESC suporta `ORDER BY ... DESC`
    # sem sort adicional.
    op.create_index(
        "ix_executions_tenant_company_started",
        "executions",
        ["tenant_id", "company_id", sa.text("started_at DESC")],
    )

    # -------------------------------------------------------------------
    # 2. Grants para app_user.
    # -------------------------------------------------------------------
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON executions TO app_user")

    # -------------------------------------------------------------------
    # 3. RLS.
    # -------------------------------------------------------------------
    op.execute("ALTER TABLE executions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE executions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY executions_isolation ON executions
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS executions_isolation ON executions")
    op.execute("ALTER TABLE IF EXISTS executions DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_executions_tenant_company_started", table_name="executions")
    op.drop_index("ix_executions_tenant_id", table_name="executions")
    op.drop_table("executions")
