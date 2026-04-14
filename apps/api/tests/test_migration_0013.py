"""Testes estaticos da migration 0013_audit_logs (DATA-05 parte 3/4)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0013_audit_logs.py"
)


def _load_migration_source() -> str:
    assert MIGRATION_PATH.exists(), f"Migration ausente: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_module_is_importable() -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_0013_audit_logs", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "0013_audit_logs"
    assert module.down_revision == "0012_schedules"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_mentions_core_fields() -> None:
    src = _load_migration_source()
    assert '"audit_logs"' in src
    for col in (
        "tenant_id",
        "actor_user_id",
        "action",
        "resource_type",
        "resource_id",
        "ip",
        "user_agent",
        "metadata",
        "created_at",
    ):
        assert f'"{col}"' in src, col
    # id BIGINT com IDENTITY (BIGSERIAL-equivalente).
    assert "BigInteger" in src
    assert "Identity" in src
    # JSONB em metadata com default '{}'.
    assert "JSONB" in src
    assert "'{}'::jsonb" in src
    # Indices exigidos.
    assert "ix_audit_logs_tenant_created_at" in src
    assert "created_at DESC" in src
    assert "ix_audit_logs_resource" in src
    # RLS + policy + GUC.
    assert "ENABLE ROW LEVEL SECURITY" in src
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "audit_logs_isolation" in src
    assert "app.current_tenant" in src
    # Grants (inclusive na sequence do IDENTITY).
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON audit_logs TO app_user" in src
    assert "audit_logs_id_seq" in src


def test_migration_has_matching_downgrade() -> None:
    src = _load_migration_source()
    assert "DROP POLICY IF EXISTS audit_logs_isolation" in src
    assert 'drop_table("audit_logs")' in src
    assert 'drop_index("ix_audit_logs_resource"' in src
    assert "ix_audit_logs_tenant_created_at" in src
