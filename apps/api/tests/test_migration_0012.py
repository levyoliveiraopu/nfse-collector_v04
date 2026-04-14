"""Testes estaticos da migration 0012_schedules (DATA-05 parte 2/4)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0012_schedules.py"
)


def _load_migration_source() -> str:
    assert MIGRATION_PATH.exists(), f"Migration ausente: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_module_is_importable() -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_0012_schedules", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "0012_schedules"
    assert module.down_revision == "0011_files"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_mentions_core_fields() -> None:
    src = _load_migration_source()
    assert '"schedules"' in src
    for col in (
        "tenant_id",
        "company_id",
        "cron_expr",
        "timezone",
        "enabled",
        "last_run_at",
        "next_run_at",
        "created_by_user_id",
    ):
        assert f'"{col}"' in src, col
    # FK composta para garantir mesmo-tenant.
    assert "fk_schedules_tenant_company" in src
    assert "companies.tenant_id" in src
    assert "companies.id" in src
    # Indice exigido pelo ticket.
    assert "ix_schedules_enabled_next_run" in src
    # RLS + policy + GUC.
    assert "ENABLE ROW LEVEL SECURITY" in src
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "schedules_isolation" in src
    assert "app.current_tenant" in src
    # Grants.
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON schedules TO app_user" in src


def test_migration_has_matching_downgrade() -> None:
    src = _load_migration_source()
    assert "DROP POLICY IF EXISTS schedules_isolation" in src
    assert 'drop_table("schedules")' in src
    assert 'drop_index("ix_schedules_enabled_next_run"' in src
    assert 'drop_index("ix_schedules_company_id"' in src
    assert 'drop_index("ix_schedules_tenant_id"' in src
