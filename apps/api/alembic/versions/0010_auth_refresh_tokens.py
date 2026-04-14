"""auth: refresh_tokens com hash, RLS e cadeia de rotacao

Revision ID: 0010_auth_refresh_tokens
Revises: 0001_initial_identity
Create Date: 2026-04-14

Entregavel do ticket API-02:
- Tabela `refresh_tokens` (opaco, armazenado como hash SHA-256 hex).
- Cadeia de rotacao via `replaced_by` (detecao de reuso).
- RLS habilitada usando o GUC `app.current_tenant` (padrao DATA-01).
- Grants DML para `app_user`.

Notas:
- O prefixo numerico 0010 deixa 0002/0003 livres para DATA-02
  (`companies` + `company_credentials`) sem precisar renumerar depois.
- A senha do refresh token nunca entra no banco em claro; apenas o
  SHA-256 hex. JWT access nao e persistido.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_auth_refresh_tokens"
down_revision: Union[str, None] = "0001_initial_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------
    # 1. refresh_tokens
    # -------------------------------------------------------------------
    op.create_table(
        "refresh_tokens",
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
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "issued_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "replaced_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip", sa.dialects.postgresql.INET(), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index(
        "ix_refresh_tokens_user_id",
        "refresh_tokens",
        ["user_id"],
    )
    op.create_index(
        "ix_refresh_tokens_tenant_id",
        "refresh_tokens",
        ["tenant_id"],
    )
    # Busca rapida por "tokens vivos de um usuario".
    op.create_index(
        "ix_refresh_tokens_user_active",
        "refresh_tokens",
        ["user_id", "expires_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    # -------------------------------------------------------------------
    # 2. Grants para app_user (DML).
    # -------------------------------------------------------------------
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON refresh_tokens TO app_user"
    )

    # -------------------------------------------------------------------
    # 3. Row Level Security por tenant_id (mesmo padrao DATA-01).
    # -------------------------------------------------------------------
    op.execute("ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE refresh_tokens FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY refresh_tokens_isolation ON refresh_tokens
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS refresh_tokens_isolation ON refresh_tokens"
    )
    op.execute(
        "ALTER TABLE IF EXISTS refresh_tokens DISABLE ROW LEVEL SECURITY"
    )

    op.drop_index("ix_refresh_tokens_user_active", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_tenant_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
