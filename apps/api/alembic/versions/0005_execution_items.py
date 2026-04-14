"""execution_items: itens processados por execucao (+ RLS)

Revision ID: 0005_execution_items
Revises: 0004_executions
Create Date: 2026-04-14

Entregavel do ticket DATA-03 (parte 2/2):
- Tabela `execution_items` com um registro por NFS-e processada dentro
  de uma `executions`.
- FK composta `(tenant_id, execution_id) -> executions(tenant_id, id)`
  ON DELETE CASCADE (defesa em profundidade — um item nao pode apontar
  para uma execucao de outro tenant).
- Indice `(execution_id)` para varrer itens de uma corrida.
- Indice `(tenant_id, data_emissao)` para consultas por competencia.
- Indice **unico parcial** `(tenant_id, chave_nfse) WHERE chave_nfse
  IS NOT NULL` — impede duplicatas da mesma NFS-e dentro do tenant sem
  bloquear linhas onde a coleta ainda nao extraiu a chave (ex.:
  `status='failed'` antes do parse).
- RLS ativada via GUC `app.current_tenant` (mesmo padrao do DATA-01).

Observacoes:
- `status` e TEXT com CHECK (`ok`, `failed`, `skipped`, `pending`).
- `cnpj_emitente` e opcional; quando presente, e validado como 14
  digitos numericos (mesmo formato do CHECK em `companies.cnpj`).
- `valor` e NUMERIC(18, 2) (precisao suficiente para NFS-e municipal).
- `xml_object_key` aponta para o XML bruto no bucket S3 sob prefixo
  `tenants/` (INFRA-06). O XML fisico vive no storage, nao no banco.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_execution_items"
down_revision: Union[str, None] = "0004_executions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EXECUTION_ITEM_STATUS = ("ok", "failed", "skipped", "pending")


def upgrade() -> None:
    # -------------------------------------------------------------------
    # 1. execution_items
    # -------------------------------------------------------------------
    op.create_table(
        "execution_items",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "execution_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nsu", sa.BigInteger(), nullable=True),
        sa.Column("chave_nfse", sa.Text(), nullable=True),
        sa.Column("cnpj_emitente", sa.Text(), nullable=True),
        sa.Column("data_emissao", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("valor", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("xml_object_key", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        # FK composta: item nao pode apontar para execucao de outro tenant.
        sa.ForeignKeyConstraint(
            ["tenant_id", "execution_id"],
            ["executions.tenant_id", "executions.id"],
            name="fk_execution_items_tenant_execution",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('ok','failed','skipped','pending')",
            name="ck_execution_items_status",
        ),
        sa.CheckConstraint(
            "cnpj_emitente IS NULL OR "
            "(char_length(cnpj_emitente) = 14 AND cnpj_emitente ~ '^[0-9]+$')",
            name="ck_execution_items_cnpj_emitente_format",
        ),
    )

    op.create_index(
        "ix_execution_items_execution_id",
        "execution_items",
        ["execution_id"],
    )
    op.create_index(
        "ix_execution_items_tenant_data_emissao",
        "execution_items",
        ["tenant_id", "data_emissao"],
    )
    # Unique parcial: evita duplicar a mesma NFS-e (chave) dentro do tenant,
    # mas tolera itens sem chave extraida (falhas precoces). Alembic suporta
    # indices parciais via `postgresql_where`.
    op.create_index(
        "uq_execution_items_tenant_chave",
        "execution_items",
        ["tenant_id", "chave_nfse"],
        unique=True,
        postgresql_where=sa.text("chave_nfse IS NOT NULL"),
    )

    # -------------------------------------------------------------------
    # 2. Grants para app_user.
    # -------------------------------------------------------------------
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON execution_items TO app_user"
    )

    # -------------------------------------------------------------------
    # 3. RLS.
    # -------------------------------------------------------------------
    op.execute("ALTER TABLE execution_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE execution_items FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY execution_items_isolation ON execution_items
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS execution_items_isolation ON execution_items"
    )
    op.execute(
        "ALTER TABLE IF EXISTS execution_items DISABLE ROW LEVEL SECURITY"
    )

    op.drop_index("uq_execution_items_tenant_chave", table_name="execution_items")
    op.drop_index(
        "ix_execution_items_tenant_data_emissao", table_name="execution_items"
    )
    op.drop_index("ix_execution_items_execution_id", table_name="execution_items")
    op.drop_table("execution_items")
