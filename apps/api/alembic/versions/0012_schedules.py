"""schedules: cron por tenant/company (+ RLS)

Revision ID: 0012_schedules
Revises: 0011_files
Create Date: 2026-04-14

Entregavel do ticket DATA-05 (parte 2/4):
- Tabela `schedules` com cron por tenant (company_id opcional para
  agendas "do tenant inteiro"), timezone por agenda, flag `enabled`,
  ponteiros `last_run_at`/`next_run_at` e ator que criou.
- Indice `(enabled, next_run_at)` para o scheduler buscar
  rapidamente o proximo job a executar (filtrando enabled = true).
- FK composta `(tenant_id, company_id) -> companies(tenant_id, id)`
  como defesa em profundidade (impede vincular company de outro
  tenant mesmo se a camada de app falhar). `company_id` e nullable;
  a FK composta aceita NULL porque ambas as colunas referencia sao
  NOT NULL mas o par (x, NULL) e considerado "match simples".
- `created_by_user_id` -> `users.id` com `ON DELETE SET NULL`
  (preservar a agenda apos remocao do usuario).
- RLS ativada via GUC `app.current_tenant` (padrao DATA-01).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_schedules"
down_revision: Union[str, None] = "0011_files"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------
    # 1. schedules
    # -------------------------------------------------------------------
    op.create_table(
        "schedules",
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
            nullable=True,
        ),
        sa.Column("cron_expr", sa.Text(), nullable=False),
        sa.Column(
            "timezone",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'America/Sao_Paulo'"),
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("last_run_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        # FK composta garante mesmo-tenant para o par.
        sa.ForeignKeyConstraint(
            ["tenant_id", "company_id"],
            ["companies.tenant_id", "companies.id"],
            name="fk_schedules_tenant_company",
            ondelete="CASCADE",
        ),
    )

    op.create_index("ix_schedules_tenant_id", "schedules", ["tenant_id"])
    op.create_index(
        "ix_schedules_company_id",
        "schedules",
        ["company_id"],
        postgresql_where=sa.text("company_id IS NOT NULL"),
    )
    # Core do scheduler: "proximo job habilitado".
    op.create_index(
        "ix_schedules_enabled_next_run",
        "schedules",
        ["enabled", "next_run_at"],
    )

    # -------------------------------------------------------------------
    # 2. Grants para app_user.
    # -------------------------------------------------------------------
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON schedules TO app_user")

    # -------------------------------------------------------------------
    # 3. RLS.
    # -------------------------------------------------------------------
    op.execute("ALTER TABLE schedules ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE schedules FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY schedules_isolation ON schedules
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS schedules_isolation ON schedules")
    op.execute("ALTER TABLE IF EXISTS schedules DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_schedules_enabled_next_run", table_name="schedules")
    op.drop_index("ix_schedules_company_id", table_name="schedules")
    op.drop_index("ix_schedules_tenant_id", table_name="schedules")
    op.drop_table("schedules")
