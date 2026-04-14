"""company_credentials: PFX A1 cifrado por CNPJ (+ RLS)

Revision ID: 0003_company_credentials
Revises: 0002_companies
Create Date: 2026-04-14

Entregavel do ticket DATA-02 (parte 2/2):
- Tabela `company_credentials` com metadados do certificado A1.
- FK composta `(tenant_id, company_id) -> companies(tenant_id, id)`
  para garantir, no nivel do banco, que uma credencial pertence ao
  mesmo tenant da company (defesa em profundidade alem da RLS).
- Indice em `cert_not_after` para suportar alertas de vencimento.
- RLS ativada via GUC `app.current_tenant`.

Observacoes de seguranca (ADR-003):
- `pfx_object_key` aponta para o bucket S3 sob prefixo `tenants/`
  (INFRA-06). O PFX fisico vive no storage, nao no banco.
- `pfx_password_ciphertext` e BYTEA: apenas o ciphertext AES-256-GCM
  (nonce + tag + ct). A chave simetrica vive em KMS/env e nao aqui.
- `type` e restrito a ('pfx_a1') nesta fase; suportar A3 seria outro
  ticket de produto e infra.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_company_credentials"
down_revision: Union[str, None] = "0002_companies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CREDENTIAL_TYPE = ("pfx_a1",)
CREDENTIAL_STATUS = ("active", "expired", "revoked", "invalid")


def upgrade() -> None:
    # -------------------------------------------------------------------
    # 1. company_credentials
    # -------------------------------------------------------------------
    op.create_table(
        "company_credentials",
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
            "type",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pfx_a1'"),
        ),
        sa.Column("pfx_object_key", sa.Text(), nullable=False),
        sa.Column("pfx_password_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("cert_fingerprint", sa.Text(), nullable=True),
        sa.Column("cert_not_before", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("cert_not_after", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("last_used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_tested_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
            name="fk_company_credentials_tenant_company",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "type IN ('pfx_a1')",
            name="ck_company_credentials_type",
        ),
        sa.CheckConstraint(
            "status IN ('active','expired','revoked','invalid')",
            name="ck_company_credentials_status",
        ),
    )

    op.create_index(
        "ix_company_credentials_tenant_id",
        "company_credentials",
        ["tenant_id"],
    )
    op.create_index(
        "ix_company_credentials_company_id",
        "company_credentials",
        ["company_id"],
    )
    # Suporta consulta de alertas "credenciais vencendo em N dias".
    op.create_index(
        "ix_company_credentials_cert_not_after",
        "company_credentials",
        ["cert_not_after"],
    )

    # -------------------------------------------------------------------
    # 2. Grants para app_user.
    # -------------------------------------------------------------------
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON company_credentials TO app_user"
    )

    # -------------------------------------------------------------------
    # 3. RLS.
    # -------------------------------------------------------------------
    op.execute("ALTER TABLE company_credentials ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE company_credentials FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY company_credentials_isolation ON company_credentials
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS company_credentials_isolation ON company_credentials"
    )
    op.execute(
        "ALTER TABLE IF EXISTS company_credentials DISABLE ROW LEVEL SECURITY"
    )

    op.drop_index(
        "ix_company_credentials_cert_not_after", table_name="company_credentials"
    )
    op.drop_index(
        "ix_company_credentials_company_id", table_name="company_credentials"
    )
    op.drop_index(
        "ix_company_credentials_tenant_id", table_name="company_credentials"
    )
    op.drop_table("company_credentials")
