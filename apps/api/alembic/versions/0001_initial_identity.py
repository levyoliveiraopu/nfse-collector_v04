"""initial identity schema: tenants, users, tenant_users (+ RLS)

Revision ID: 0001_initial_identity
Revises:
Create Date: 2026-04-14

Entregavel do ticket DATA-01:
- Extensao `pgcrypto` (gen_random_uuid()).
- Roles `app_admin` (BYPASSRLS) e `app_user` (NOBYPASSRLS).
- Tabelas `tenants`, `users`, `tenant_users`.
- RLS habilitada em `tenants` e `tenant_users` com politicas que leem
  o GUC `app.current_tenant`.
- Grants para `app_user`.

Observacoes:
- `users` e tabela global de identidade (um mesmo usuario pode pertencer
  a varios tenants). O isolamento por tenant e enforced em `tenant_users`
  via RLS. `users` nao tem RLS.
- `tenants.plan_id` fica `TEXT NULL` por ora; DATA-05 criara `plans(code)`
  e promovera essa coluna a FK.
- Policies usam `current_setting('app.current_tenant', true)::uuid`,
  com `true` para evitar erro quando a GUC nao estiver setada
  (retorna NULL e a condicao fica falsa, bloqueando acesso).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_identity"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TENANT_STATUS = ("trial", "active", "suspended", "canceled")
USER_STATUS = ("invited", "active", "disabled")
TENANT_USER_ROLE = ("owner", "admin", "operator", "viewer")


def upgrade() -> None:
    # -------------------------------------------------------------------
    # 1. Extensoes
    # -------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # -------------------------------------------------------------------
    # 2. Roles (idempotentes; nao sao dropadas em downgrade se tiverem
    #    objetos dependentes em outros schemas).
    # -------------------------------------------------------------------
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
                CREATE ROLE app_admin NOLOGIN BYPASSRLS;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                CREATE ROLE app_user NOLOGIN NOBYPASSRLS;
            END IF;
        END
        $$;
        """
    )

    # -------------------------------------------------------------------
    # 3. tenants
    # -------------------------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("plan_id", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'trial'"),
        ),
        sa.Column("trial_ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("billing_email", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
        sa.CheckConstraint(
            "status IN ('trial','active','suspended','canceled')",
            name="ck_tenants_status",
        ),
    )

    # -------------------------------------------------------------------
    # 4. users (tabela global de identidade — sem tenant_id, sem RLS)
    # -------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("mfa_secret", sa.Text(), nullable=True),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'active'"),
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
        sa.CheckConstraint(
            "status IN ('invited','active','disabled')",
            name="ck_users_status",
        ),
    )
    # Unico case-insensitive em email.
    op.execute(
        "CREATE UNIQUE INDEX uq_users_email_lower ON users (LOWER(email))"
    )

    # -------------------------------------------------------------------
    # 5. tenant_users (N:N com atributos)
    # -------------------------------------------------------------------
    op.create_table(
        "tenant_users",
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
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("invited_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("tenant_id", "user_id", name="pk_tenant_users"),
        sa.CheckConstraint(
            "role IN ('owner','admin','operator','viewer')",
            name="ck_tenant_users_role",
        ),
    )
    op.create_index(
        "ix_tenant_users_user_id",
        "tenant_users",
        ["user_id"],
    )
    op.create_index(
        "ix_tenant_users_tenant_role",
        "tenant_users",
        ["tenant_id", "role"],
    )

    # -------------------------------------------------------------------
    # 6. Grants para app_user (DML). app_admin herda de superuser/migrator.
    # -------------------------------------------------------------------
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tenants TO app_user")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON users TO app_user")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_users TO app_user"
    )

    # -------------------------------------------------------------------
    # 7. Row Level Security em tenants e tenant_users.
    #
    # `current_setting('app.current_tenant', true)` retorna NULL quando a
    # GUC nao esta setada (o segundo argumento `true` significa
    # "missing_ok"). Nesse caso a condicao `id = NULL::uuid` e falsa,
    # bloqueando qualquer leitura/escrita — fail-closed.
    # -------------------------------------------------------------------
    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenants_isolation ON tenants
            USING (id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )

    op.execute("ALTER TABLE tenant_users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_users FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_users_isolation ON tenant_users
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )


def downgrade() -> None:
    # Derruba policies antes das tabelas.
    op.execute("DROP POLICY IF EXISTS tenant_users_isolation ON tenant_users")
    op.execute("ALTER TABLE IF EXISTS tenant_users DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS tenants_isolation ON tenants")
    op.execute("ALTER TABLE IF EXISTS tenants DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_tenant_users_tenant_role", table_name="tenant_users")
    op.drop_index("ix_tenant_users_user_id", table_name="tenant_users")
    op.drop_table("tenant_users")

    op.execute("DROP INDEX IF EXISTS uq_users_email_lower")
    op.drop_table("users")

    op.drop_table("tenants")

    # Remove privilegios residuais antes de dropar roles.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                EXECUTE 'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_user';
                EXECUTE 'REVOKE ALL ON SCHEMA public FROM app_user';
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
                EXECUTE 'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_admin';
                EXECUTE 'REVOKE ALL ON SCHEMA public FROM app_admin';
            END IF;
        END
        $$;
        """
    )
    op.execute("DROP ROLE IF EXISTS app_user")
    op.execute("DROP ROLE IF EXISTS app_admin")

    # Extensao `pgcrypto` e deliberadamente preservada: pode estar em uso
    # por outros schemas/migrations fora deste escopo.
