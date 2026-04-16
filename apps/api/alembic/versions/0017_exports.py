"""exports: pedidos de export assincrono (+ RLS)

Revision ID: 0017_exports
Revises: 0016_merge_0015_heads
Create Date: 2026-04-16

Entregavel do ticket API-15 (Export ZIP assincrono).

Modelagem:
- `exports` registra um pedido de export assincrono (`POST /exports`).
  A linha nasce em `status='queued'`, passa para `running` quando o
  worker pica o job e termina em `ready` (sucesso) ou `failed`.
- Quando termina com sucesso, `file_id` aponta para a linha criada em
  `files` (kind='export'), e o caller baixa pelo endpoint existente
  `GET /files/{id}/url` (API-11).
- Tabela dedicada (em vez de reusar `files`) porque "pedido de export"
  tem ciclo de vida proprio (status/period/kind/contadores/erro) e
  `files` e deliberadamente enxuta (ADR-003, "Sem storage_tier").

Campos:
- `kind` CHECK em `('zip_xml',)` hoje. O ticket API-15 prevê
  `excel_consolidated` como kind futuro; mantemos so `zip_xml` neste
  MVP para nao expor caminho morto na API. Extensao do enum vira
  migration separada no ticket que implementar o consolidado.
- `status` CHECK em `('queued','running','ready','failed','empty')`.
  `empty` = finalizou sem itens para exportar (periodo vazio); e
  diferenciado de `failed` para a UI mostrar mensagem especifica.
- `company_id` e obrigatorio (escopo empresa/periodo, como pede o
  ticket). Sem FK composta pra manter a migration simples; o handler
  valida a company via RLS de `companies`.
- `file_id` nullable: preenchido quando o worker finaliza com sucesso.
- `requested_by_user_id` FK para users com ON DELETE SET NULL
  (preserva historico mesmo apos remocao do usuario).
- `items_count` / `total_bytes` diagnostico pos-mortem.
- `error_code` / `error_message`: `size_limit_exceeded`, `no_items`,
  `s3_error`, `unexpected` — UI traduz em mensagem.

Indices:
- `(tenant_id, created_at DESC)` para timeline do painel.
- `(tenant_id, status) WHERE status IN ('queued','running')` parcial
  para o worker/admin procurarem pedidos em voo.

RLS: identica ao padrao DATA-01 (GUC `app.current_tenant`).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017_exports"
down_revision: Union[str, None] = "0016_merge_0015_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EXPORT_KIND = ("zip_xml",)
EXPORT_STATUS = ("queued", "running", "ready", "failed", "empty")


def upgrade() -> None:
    op.create_table(
        "exports",
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
        sa.Column(
            "requested_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column(
            "file_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("files.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "items_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "total_bytes",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
            "kind IN ('zip_xml')",
            name="ck_exports_kind",
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','ready','failed','empty')",
            name="ck_exports_status",
        ),
        sa.CheckConstraint(
            "period_end >= period_start",
            name="ck_exports_period_order",
        ),
        sa.CheckConstraint(
            "items_count >= 0 AND total_bytes >= 0",
            name="ck_exports_counters_nonneg",
        ),
    )

    op.create_index(
        "ix_exports_tenant_created",
        "exports",
        ["tenant_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_exports_tenant_company",
        "exports",
        ["tenant_id", "company_id"],
    )
    # Parcial: worker e admin pesquisam pedidos em voo com frequencia.
    op.create_index(
        "ix_exports_inflight",
        "exports",
        ["tenant_id", "status"],
        postgresql_where=sa.text("status IN ('queued','running')"),
    )

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON exports TO app_user")

    op.execute("ALTER TABLE exports ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE exports FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY exports_isolation ON exports
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS exports_isolation ON exports")
    op.execute("ALTER TABLE IF EXISTS exports DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_exports_inflight", table_name="exports")
    op.drop_index("ix_exports_tenant_company", table_name="exports")
    op.drop_index("ix_exports_tenant_created", table_name="exports")
    op.drop_table("exports")
