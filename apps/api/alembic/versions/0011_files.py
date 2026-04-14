"""files: objetos armazenados no S3 (+ RLS) e merge de heads Alembic

Revision ID: 0011_files
Revises: 0003_company_credentials, 0010_auth_refresh_tokens
Create Date: 2026-04-14

Entregavel do ticket DATA-05 (parte 1/4):
- Tabela `files` (id, tenant_id, kind, object_key, bytes,
  checksum_sha256, source_execution_id, expires_at, timestamps).
- **Sem `storage_tier`** (ADR-003: retencao 90d sem arquivamento; nao
  ha tiers de storage no nosso modelo).
- RLS ativada via GUC `app.current_tenant` (padrao DATA-01).

Observacao — merge de heads Alembic:
- Ate aqui a arvore tinha dois heads: `0003_company_credentials`
  (cadeia DATA-02) e `0010_auth_refresh_tokens` (cadeia API-02, que
  saltou a numeracao para deixar 0002/0003 livres). Esta migration
  funciona como ponto de merge explicito dos dois ramos, deixando a
  arvore linear novamente. A partir daqui `alembic upgrade head`
  resolve sem ambiguidade.

Observacoes de modelagem:
- `kind` e TEXT + CHECK com o enum operacional (`nfse_xml`, `export`,
  `pfx`, `report`, `other`). PFX vive aqui tambem como referencia
  canonica do objeto S3 (apontado tambem por `company_credentials`).
- `object_key` segue o layout do INFRA-06: `tenants/<tenant>/...` ou
  `tenants-exports/<tenant>/...`. Nao validamos o prefixo no DB para
  nao acoplar a migration ao bucket — fica na camada de aplicacao.
- `checksum_sha256` e hex de 64 chars (CHECK formal).
- `bytes` e BIGINT (XMLs pequenos, exports podem passar de 2GB).
- `source_execution_id` e UUID nullable (liga ao execution do worker;
  a tabela de executions vem em CORE-* e nao e FK hoje, para nao
  acoplar DATA a CORE).
- `expires_at` suporta o lifecycle de 90d (ADR-003): o worker/cron
  compara com `now()` para purgar. Indice partial para nao penalizar
  inserts com `expires_at NULL`.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_files"
down_revision: Union[str, Sequence[str], None] = (
    "0003_company_credentials",
    "0010_auth_refresh_tokens",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FILE_KIND = ("nfse_xml", "export", "pfx", "report", "other")


def upgrade() -> None:
    # -------------------------------------------------------------------
    # 1. files
    # -------------------------------------------------------------------
    op.create_table(
        "files",
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
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.Text(), nullable=False),
        sa.Column(
            "source_execution_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "tenant_id", "object_key", name="uq_files_tenant_object_key"
        ),
        sa.CheckConstraint(
            "kind IN ('nfse_xml','export','pfx','report','other')",
            name="ck_files_kind",
        ),
        sa.CheckConstraint(
            "char_length(checksum_sha256) = 64 AND checksum_sha256 ~ '^[0-9a-f]+$'",
            name="ck_files_checksum_sha256_hex",
        ),
        sa.CheckConstraint("bytes >= 0", name="ck_files_bytes_nonneg"),
    )

    op.create_index("ix_files_tenant_id", "files", ["tenant_id"])
    # Partial: suporta o cron de expurgo sem penalizar linhas com NULL.
    op.create_index(
        "ix_files_expires_at",
        "files",
        ["expires_at"],
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )
    op.create_index(
        "ix_files_source_execution_id",
        "files",
        ["source_execution_id"],
        postgresql_where=sa.text("source_execution_id IS NOT NULL"),
    )

    # -------------------------------------------------------------------
    # 2. Grants para app_user.
    # -------------------------------------------------------------------
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON files TO app_user")

    # -------------------------------------------------------------------
    # 3. RLS.
    # -------------------------------------------------------------------
    op.execute("ALTER TABLE files ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE files FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY files_isolation ON files
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS files_isolation ON files")
    op.execute("ALTER TABLE IF EXISTS files DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_files_source_execution_id", table_name="files")
    op.drop_index("ix_files_expires_at", table_name="files")
    op.drop_index("ix_files_tenant_id", table_name="files")
    op.drop_table("files")
