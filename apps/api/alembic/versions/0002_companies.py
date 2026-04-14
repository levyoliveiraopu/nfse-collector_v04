"""companies: CNPJs por tenant (+ RLS)

Revision ID: 0002_companies
Revises: 0001_initial_identity
Create Date: 2026-04-14

Entregavel do ticket DATA-02 (parte 1/2):
- Tabela `companies` com atributos operacionais do CNPJ (razao social,
  municipio IBGE, UF, status operacional, controle de NSU e portal).
- Unico por `(tenant_id, cnpj)` (um mesmo CNPJ pode existir em tenants
  diferentes em cenarios de contabilidade/multi-workspace).
- UNIQUE(tenant_id, id) habilita FK composta em `company_credentials`
  (defesa em profundidade alem da RLS — impede vinculacao cross-tenant
  via DB, nao apenas via aplicacao).
- RLS ativada via GUC `app.current_tenant` (mesmo padrao do DATA-01).

Observacoes:
- `cnpj` e TEXT com CHECK de 14 digitos numericos (armazenamos apenas
  digitos normalizados; formatacao fica na camada de apresentacao).
- `portal_provider` e TEXT livre por ora; CORE-* ira canonizar os slugs.
- `municipio_ibge` e TEXT (evita decisao prematura sobre INTEGER).
- `last_nsu` e BIGINT (NSU de alguns portais cresce rapidamente).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_companies"
down_revision: Union[str, None] = "0001_initial_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COMPANY_STATUS = ("active", "paused", "disabled")


def upgrade() -> None:
    # -------------------------------------------------------------------
    # 1. companies
    # -------------------------------------------------------------------
    op.create_table(
        "companies",
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
        sa.Column("cnpj", sa.Text(), nullable=False),
        sa.Column("razao_social", sa.Text(), nullable=False),
        sa.Column("nome_fantasia", sa.Text(), nullable=True),
        sa.Column("municipio_ibge", sa.Text(), nullable=False),
        sa.Column("uf", sa.CHAR(length=2), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("last_nsu", sa.BigInteger(), nullable=True),
        sa.Column("last_success_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("portal_provider", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("tenant_id", "cnpj", name="uq_companies_tenant_cnpj"),
        # UNIQUE(tenant_id, id) habilita FK composta em company_credentials.
        sa.UniqueConstraint("tenant_id", "id", name="uq_companies_tenant_id_id"),
        sa.CheckConstraint(
            "status IN ('active','paused','disabled')",
            name="ck_companies_status",
        ),
        sa.CheckConstraint(
            "char_length(cnpj) = 14 AND cnpj ~ '^[0-9]+$'",
            name="ck_companies_cnpj_format",
        ),
    )

    op.create_index(
        "ix_companies_tenant_id",
        "companies",
        ["tenant_id"],
    )

    # -------------------------------------------------------------------
    # 2. Grants para app_user.
    # -------------------------------------------------------------------
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON companies TO app_user")

    # -------------------------------------------------------------------
    # 3. RLS em companies (mesmo padrao do DATA-01).
    # -------------------------------------------------------------------
    op.execute("ALTER TABLE companies ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE companies FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY companies_isolation ON companies
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS companies_isolation ON companies")
    op.execute("ALTER TABLE IF EXISTS companies DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_companies_tenant_id", table_name="companies")
    op.drop_table("companies")
