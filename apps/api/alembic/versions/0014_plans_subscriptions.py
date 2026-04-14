"""plans + subscriptions: catalogo global + assinatura por tenant

Revision ID: 0014_plans_subscriptions
Revises: 0013_audit_logs
Create Date: 2026-04-14

Entregavel do ticket DATA-05 (parte 4/4):
- Tabela `plans` (catalogo global, sem RLS): `code` PK, `name`,
  `limits jsonb`, `price_cents`, `active`, timestamps.
- Tabela `subscriptions` (por tenant, com RLS): `tenant_id` unico,
  `plan_id` FK -> `plans(code)`, `status`, janela do periodo,
  metadados do gateway.
- Promove `tenants.plan_id` a FK -> `plans(code)` (nota do DATA-01:
  "DATA-05 promovera essa coluna a FK"). Mantem nullable para nao
  quebrar tenants existentes em `trial` sem plano definido.
- Billing adiado (ADR-004): schema pronto, mas `gateway*` e
  `subscriptions` podem ser populados numa fase posterior sem nova
  migration.

Observacoes:
- `plans.code` e o identificador publico (`free`, `pro`, `scale`) —
  usado como FK em `tenants.plan_id` e `subscriptions.plan_id`. Uma
  UUID interna adicionaria indirecao sem beneficio: o catalogo e
  pequeno e estavel.
- `subscriptions` tem UNIQUE em `tenant_id` porque no MVP cada tenant
  tem no maximo uma assinatura ativa. Upgrade/downgrade de plano se
  da por UPDATE, nao por inserir nova linha.
- `status` e TEXT + CHECK com o vocabulario do Stripe/Iugu
  (`trialing`, `active`, `past_due`, `canceled`, `paused`). Nao
  usamos ENUM nativo para evitar custo de migration em novos
  estados.
- Sem RLS em `plans`: e catalogo global, igual para todos os tenants.
  So concedemos SELECT para `app_user` (DML reservado a migracoes /
  admin).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014_plans_subscriptions"
down_revision: Union[str, None] = "0013_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SUBSCRIPTION_STATUS = (
    "trialing",
    "active",
    "past_due",
    "canceled",
    "paused",
)


def upgrade() -> None:
    # -------------------------------------------------------------------
    # 1. plans (catalogo global)
    # -------------------------------------------------------------------
    op.create_table(
        "plans",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "limits",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
        sa.CheckConstraint("price_cents >= 0", name="ck_plans_price_nonneg"),
        sa.CheckConstraint(
            "code ~ '^[a-z0-9_-]+$'",
            name="ck_plans_code_format",
        ),
    )

    # SELECT para app_user; DML reservado a migracoes / admin role.
    op.execute("GRANT SELECT ON plans TO app_user")

    # -------------------------------------------------------------------
    # 2. tenants.plan_id -> plans.code (promocao da coluna existente)
    # -------------------------------------------------------------------
    # Mantem nullable; tenants em trial podem nao ter plano.
    op.create_foreign_key(
        "fk_tenants_plan",
        source_table="tenants",
        referent_table="plans",
        local_cols=["plan_id"],
        remote_cols=["code"],
        ondelete="RESTRICT",
    )

    # -------------------------------------------------------------------
    # 3. subscriptions (por tenant, com RLS)
    # -------------------------------------------------------------------
    op.create_table(
        "subscriptions",
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
            "plan_id",
            sa.Text(),
            sa.ForeignKey("plans.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'trialing'"),
        ),
        sa.Column(
            "current_period_start",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "current_period_end",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column("gateway", sa.Text(), nullable=True),
        sa.Column("gateway_customer_id", sa.Text(), nullable=True),
        sa.Column("gateway_subscription_id", sa.Text(), nullable=True),
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
            "tenant_id", name="uq_subscriptions_tenant_id"
        ),
        sa.CheckConstraint(
            "status IN ('trialing','active','past_due','canceled','paused')",
            name="ck_subscriptions_status",
        ),
    )

    op.create_index(
        "ix_subscriptions_plan_id",
        "subscriptions",
        ["plan_id"],
    )
    op.create_index(
        "ix_subscriptions_status",
        "subscriptions",
        ["status"],
    )

    # Grants para app_user.
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON subscriptions TO app_user"
    )

    # RLS.
    op.execute("ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE subscriptions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY subscriptions_isolation ON subscriptions
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS subscriptions_isolation ON subscriptions"
    )
    op.execute(
        "ALTER TABLE IF EXISTS subscriptions DISABLE ROW LEVEL SECURITY"
    )

    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_plan_id", table_name="subscriptions")
    op.drop_table("subscriptions")

    # Remove FK tenants.plan_id -> plans.code antes de dropar plans.
    op.drop_constraint("fk_tenants_plan", "tenants", type_="foreignkey")

    op.execute("REVOKE ALL ON plans FROM app_user")
    op.drop_table("plans")
