"""Testes estaticos da migration 0008_notifications (DATA-04 parte 3/3).

Nao se conectam ao Postgres: validam que a migration existe, pode ser
importada e contem os elementos chave (tabela, FKs, payload jsonb,
CHECKs de channel/status, indice parcial para pendentes, RLS,
politica, GUC, grants, downgrade simetrico).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0008_notifications.py"
)


def _load_migration_source() -> str:
    assert MIGRATION_PATH.exists(), f"Migration ausente: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_module_is_importable() -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_0008_notifications", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "0008_notifications"
    assert module.down_revision == "0007_reprocess_jobs"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_mentions_core_entities() -> None:
    src = _load_migration_source()
    # Tabela.
    assert '"notifications"' in src or "'notifications'" in src
    # Colunas exigidas pelo ticket.
    for col in (
        "tenant_id",
        "user_id",
        "channel",
        "type",
        "payload",
        "status",
        "sent_at",
        "read_at",
    ):
        assert col in src, col
    # FKs.
    assert "tenants.id" in src
    assert "users.id" in src
    # JSONB.
    assert "JSONB" in src
    # CHECKs.
    assert "ck_notifications_channel" in src
    assert "ck_notifications_status" in src
    # Indices (incluindo o parcial de pendentes).
    for idx in (
        "ix_notifications_tenant_id",
        "ix_notifications_tenant_user_status",
        "ix_notifications_tenant_created",
        "ix_notifications_pending",
    ):
        assert idx in src, idx
    # Indice parcial exibe WHERE.
    assert "postgresql_where" in src
    # RLS + GUC.
    assert "ENABLE ROW LEVEL SECURITY" in src
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "app.current_tenant" in src
    assert "notifications_isolation" in src
    # Grants.
    assert (
        "GRANT SELECT, INSERT, UPDATE, DELETE ON notifications TO app_user"
        in src
    )


def test_migration_has_matching_downgrade() -> None:
    src = _load_migration_source()
    assert "DROP POLICY IF EXISTS notifications_isolation" in src
    assert 'drop_table("notifications")' in src
    for idx in (
        "ix_notifications_pending",
        "ix_notifications_tenant_created",
        "ix_notifications_tenant_user_status",
        "ix_notifications_tenant_id",
    ):
        assert f'"{idx}"' in src, idx
        assert "drop_index" in src
