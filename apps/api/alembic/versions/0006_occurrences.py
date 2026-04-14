"""occurrences: ocorrencias operacionais por tenant (+ RLS)

Revision ID: 0006_occurrences
Revises: 0005_execution_items
Create Date: 2026-04-14

Entregavel do ticket DATA-04 (parte 1/3):
- Tabela `occurrences` para ocorrencias operacionais (certificado
  vencendo, credencial invalida, portal instavel, item que precisa
  reprocessar, etc.). O codigo do dominio (`code`) e livre aqui e sera
  canonizado pelos tickets CORE-*/APP-06 (ex.: `CERT_EXPIRED`,
  `CRED_INVALID`, `PORTAL_5XX`, `REPROCESS_NEEDED`).
- FK composta `(tenant_id, company_id) -> companies(tenant_id, id)`
  como defesa em profundidade (mesmo padrao de `company_credentials` e
  `executions`: impede no banco que uma ocorrencia aponte para uma
  company de outro tenant, alem da RLS).
- FK composta `(tenant_id, execution_id) -> executions(tenant_id, id)`
  nullable com `ON DELETE SET NULL`: nem toda ocorrencia pertence a uma
  execucao (ex.: alerta de certificado vencendo detectado por job de
  varredura), e queremos preservar o historico caso a execucao seja
  purgada pela retencao de 90d (ADR-003).
- `assignee_user_id` -> `users(id)` nullable com `ON DELETE SET NULL`
  (preserva o historico mesmo se o usuario for removido; `users` e
  global, sem `tenant_id`).
- Indice `(tenant_id, status)` acelera "ocorrencias abertas deste
  tenant"; `(tenant_id, company_id)` acelera o drill-down por CNPJ;
  `(execution_id)` suporta o link reverso a partir de uma execucao.
- RLS ativada via GUC `app.current_tenant` (mesmo padrao do DATA-01).

Observacoes:
- `severity` e TEXT com CHECK (`info`, `warning`, `error`, `critical`).
- `status` e TEXT com CHECK (`open`, `ack`, `snoozed`, `resolved`,
  `ignored`). `ack` = reconhecida mas ainda aberta; `snoozed` = adiada
  com `last_seen_at` futura para re-alerta.
- `first_seen_at`/`last_seen_at` permitem deduplicar a mesma ocorrencia
  (ex.: portal 5xx repetido) sem criar linhas novas — o codigo da
  aplicacao faz upsert por `(tenant_id, company_id, code)` se quiser.
- `detail` e TEXT livre (pode carregar JSON serializado ou mensagem
  longa do portal); nao normalizamos para evitar decisao prematura.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_occurrences"
down_revision: Union[str, None] = "0005_execution_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OCCURRENCE_SEVERITY = ("info", "warning", "error", "critical")
OCCURRENCE_STATUS = ("open", "ack", "snoozed", "resolved", "ignored")


def upgrade() -> None:
    # -------------------------------------------------------------------
    # 1. occurrences
    # -------------------------------------------------------------------
    op.create_table(
        "occurrences",
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
            "execution_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column(
            "assignee_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "first_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
            name="fk_occurrences_tenant_company",
            ondelete="CASCADE",
        ),
        # FK composta para executions: garante mesmo tenant. SET NULL para
        # preservar a ocorrencia se a execucao for purgada (retencao 90d).
        sa.ForeignKeyConstraint(
            ["tenant_id", "execution_id"],
            ["executions.tenant_id", "executions.id"],
            name="fk_occurrences_tenant_execution",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "severity IN ('info','warning','error','critical')",
            name="ck_occurrences_severity",
        ),
        sa.CheckConstraint(
            "status IN ('open','ack','snoozed','resolved','ignored')",
            name="ck_occurrences_status",
        ),
        sa.CheckConstraint(
            "last_seen_at >= first_seen_at",
            name="ck_occurrences_seen_order",
        ),
    )

    op.create_index(
        "ix_occurrences_tenant_id",
        "occurrences",
        ["tenant_id"],
    )
    op.create_index(
        "ix_occurrences_tenant_status",
        "occurrences",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_occurrences_tenant_company",
        "occurrences",
        ["tenant_id", "company_id"],
    )
    op.create_index(
        "ix_occurrences_execution_id",
        "occurrences",
        ["execution_id"],
    )

    # -------------------------------------------------------------------
    # 2. Grants para app_user.
    # -------------------------------------------------------------------
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON occurrences TO app_user")

    # -------------------------------------------------------------------
    # 3. RLS.
    # -------------------------------------------------------------------
    op.execute("ALTER TABLE occurrences ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE occurrences FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY occurrences_isolation ON occurrences
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS occurrences_isolation ON occurrences")
    op.execute("ALTER TABLE IF EXISTS occurrences DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_occurrences_execution_id", table_name="occurrences")
    op.drop_index("ix_occurrences_tenant_company", table_name="occurrences")
    op.drop_index("ix_occurrences_tenant_status", table_name="occurrences")
    op.drop_index("ix_occurrences_tenant_id", table_name="occurrences")
    op.drop_table("occurrences")
