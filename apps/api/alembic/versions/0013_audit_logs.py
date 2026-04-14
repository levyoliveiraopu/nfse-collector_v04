"""audit_logs: trilha append-only de acoes de usuario (+ RLS)

Revision ID: 0013_audit_logs
Revises: 0012_schedules
Create Date: 2026-04-14

Entregavel do ticket DATA-05 (parte 3/4):
- Tabela `audit_logs` com `id bigserial`, `tenant_id`, `actor_user_id`
  nullable, `action`, `resource_type`, `resource_id`, `ip inet`,
  `user_agent`, `metadata jsonb`, `created_at`.
- Indice `(tenant_id, created_at DESC)` para timeline do tenant.
- Indice `(resource_type, resource_id)` para auditoria por recurso.
- RLS ativada via GUC `app.current_tenant` (padrao DATA-01).

Observacoes:
- `id` e BIGSERIAL (BIGINT autoincrement) — trilha pode crescer rapido
  e UUID aqui nao traz vantagem semantica.
- `actor_user_id` e FK para `users(id)` com `ON DELETE SET NULL` para
  preservar o historico mesmo apos o usuario ser removido.
- `resource_id` e TEXT (nao UUID) porque auditamos tipos heterogeneos
  (UUID, bigint de audit_logs, string de `tenants.slug`, etc).
- `metadata` tem default `'{}'::jsonb` para permitir eventos sem
  payload extra sem precisar passar `{}` explicitamente no INSERT.
- Mantemos GRANTs DML completos; a convencao "append-only" e
  enforced na camada de aplicacao (nao criamos trigger de bloqueio
  de UPDATE/DELETE para nao acoplar a convencao ao schema).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_audit_logs"
down_revision: Union[str, None] = "0012_schedules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------
    # 1. audit_logs
    # -------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=True),
        sa.Column("ip", sa.dialects.postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Timeline do tenant (mais recente primeiro).
    op.execute(
        "CREATE INDEX ix_audit_logs_tenant_created_at "
        "ON audit_logs (tenant_id, created_at DESC)"
    )
    # Auditoria por recurso.
    op.create_index(
        "ix_audit_logs_resource",
        "audit_logs",
        ["resource_type", "resource_id"],
    )

    # -------------------------------------------------------------------
    # 2. Grants para app_user.
    # -------------------------------------------------------------------
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON audit_logs TO app_user"
    )
    # BIGSERIAL/IDENTITY sequence precisa de USAGE para INSERT funcionar.
    op.execute(
        """
        DO $$
        BEGIN
            PERFORM 1 FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
              WHERE c.relkind = 'S'
                AND n.nspname = 'public'
                AND c.relname = 'audit_logs_id_seq';
            IF FOUND THEN
                EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE audit_logs_id_seq TO app_user';
            END IF;
        END
        $$;
        """
    )

    # -------------------------------------------------------------------
    # 3. RLS.
    # -------------------------------------------------------------------
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY audit_logs_isolation ON audit_logs
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_logs_isolation ON audit_logs")
    op.execute("ALTER TABLE IF EXISTS audit_logs DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_audit_logs_resource", table_name="audit_logs")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_tenant_created_at")
    op.drop_table("audit_logs")
