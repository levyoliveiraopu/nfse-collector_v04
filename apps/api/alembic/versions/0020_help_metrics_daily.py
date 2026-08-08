"""Metricas diarias e anonimizadas da ajuda contextual.

Revision ID: 0020_help_metrics_daily
Revises: 0019_export_excel_nfse
Create Date: 2026-08-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_help_metrics_daily"
down_revision: Union[str, None] = "0019_export_excel_nfse"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EVENTS = (
    "article_opened",
    "search_performed",
    "search_no_results",
    "tour_started",
    "tour_completed",
    "tour_skipped",
    "tour_failed",
    "feedback_yes",
    "feedback_no",
)


def upgrade() -> None:
    event_values = ",".join(f"'{value}'" for value in _EVENTS)
    op.create_table(
        "help_metrics_daily",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("article_slug", sa.Text(), nullable=False, server_default=""),
        sa.Column("route_key", sa.Text(), nullable=False, server_default=""),
        sa.Column("tour_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("count", sa.BigInteger(), nullable=False, server_default="1"),
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
        sa.PrimaryKeyConstraint(
            "tenant_id",
            "day",
            "role",
            "event_type",
            "article_slug",
            "route_key",
            "tour_id",
            name="pk_help_metrics_daily",
        ),
        sa.CheckConstraint(
            "role IN ('owner','admin','operator','viewer')",
            name="ck_help_metrics_daily_role",
        ),
        sa.CheckConstraint(
            f"event_type IN ({event_values})",
            name="ck_help_metrics_daily_event_type",
        ),
        sa.CheckConstraint("count > 0", name="ck_help_metrics_daily_count"),
    )
    op.execute(
        "CREATE INDEX ix_help_metrics_tenant_day "
        "ON help_metrics_daily (tenant_id, day DESC)"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON help_metrics_daily TO app_user"
    )
    op.execute("ALTER TABLE help_metrics_daily ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE help_metrics_daily FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY help_metrics_daily_isolation ON help_metrics_daily
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS help_metrics_daily_isolation ON help_metrics_daily"
    )
    op.execute(
        "ALTER TABLE IF EXISTS help_metrics_daily DISABLE ROW LEVEL SECURITY"
    )
    op.execute("DROP INDEX IF EXISTS ix_help_metrics_tenant_day")
    op.drop_table("help_metrics_daily")
