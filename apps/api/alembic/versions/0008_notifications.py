"""notifications: outbox de notificacoes multicanal (+ RLS)

Revision ID: 0008_notifications
Revises: 0007_reprocess_jobs
Create Date: 2026-04-14

Entregavel do ticket DATA-04 (parte 3/3):
- Tabela `notifications` como outbox de notificacoes que o worker
  entrega por canal (in-app/email/webhook/sms). O shape especifico de
  cada `type` fica em `payload` (JSONB) e sera canonizado pelos
  tickets de API/DS/APP que consumirem (ex.: `occurrence.opened`,
  `reprocess.finished`, `cert.expiring_soon`).
- `user_id` e nullable: notificacoes direcionadas tem `user_id`;
  broadcasts por tenant (ex.: alerta operacional para todos os admins)
  tem `user_id IS NULL`.
- `user_id -> users(id)` com `ON DELETE CASCADE`: se o usuario for
  removido, suas notificacoes direcionadas tambem somem. Broadcasts
  (user_id NULL) sao preservados.
- RLS ativada via GUC `app.current_tenant`.

Observacoes:
- `channel` com CHECK (`inapp`, `email`, `webhook`, `sms`).
- `status` com CHECK (`pending`, `sent`, `failed`, `read`). `read` vale
  sobretudo para o canal `inapp`; outros canais podem manter `sent`.
- Indice `(tenant_id, user_id, status)` acelera a caixa inline do
  painel ("nao lidas deste usuario neste tenant").
- Indice `(tenant_id, created_at DESC)` acelera a listagem cronologica.
- Indice parcial `(tenant_id, status) WHERE status IN ('pending','failed')`
  acelera o loop do worker (buscar notificacoes pendentes para entregar).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_notifications"
down_revision: Union[str, None] = "0007_reprocess_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NOTIFICATION_CHANNEL = ("inapp", "email", "webhook", "sms")
NOTIFICATION_STATUS = ("pending", "sent", "failed", "read")


def upgrade() -> None:
    # -------------------------------------------------------------------
    # 1. notifications
    # -------------------------------------------------------------------
    op.create_table(
        "notifications",
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
            nullable=True,
        ),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("read_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
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
            "channel IN ('inapp','email','webhook','sms')",
            name="ck_notifications_channel",
        ),
        sa.CheckConstraint(
            "status IN ('pending','sent','failed','read')",
            name="ck_notifications_status",
        ),
    )

    op.create_index(
        "ix_notifications_tenant_id",
        "notifications",
        ["tenant_id"],
    )
    op.create_index(
        "ix_notifications_tenant_user_status",
        "notifications",
        ["tenant_id", "user_id", "status"],
    )
    op.create_index(
        "ix_notifications_tenant_created",
        "notifications",
        ["tenant_id", sa.text("created_at DESC")],
    )
    # Indice parcial para o loop do worker (entrega de pendentes/retry
    # de falhas). Mantem o indice pequeno ao excluir `sent`/`read`.
    op.create_index(
        "ix_notifications_pending",
        "notifications",
        ["tenant_id", "status"],
        postgresql_where=sa.text("status IN ('pending','failed')"),
    )

    # -------------------------------------------------------------------
    # 2. Grants para app_user.
    # -------------------------------------------------------------------
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON notifications TO app_user"
    )

    # -------------------------------------------------------------------
    # 3. RLS.
    # -------------------------------------------------------------------
    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notifications FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY notifications_isolation ON notifications
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS notifications_isolation ON notifications"
    )
    op.execute(
        "ALTER TABLE IF EXISTS notifications DISABLE ROW LEVEL SECURITY"
    )

    op.drop_index("ix_notifications_pending", table_name="notifications")
    op.drop_index("ix_notifications_tenant_created", table_name="notifications")
    op.drop_index(
        "ix_notifications_tenant_user_status", table_name="notifications"
    )
    op.drop_index("ix_notifications_tenant_id", table_name="notifications")
    op.drop_table("notifications")
