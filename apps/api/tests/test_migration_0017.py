"""Testes estaticos das migrations 0017 (API-08 e API-15).

Nao conectam ao Postgres: validam que os arquivos existem, podem ser
importados e contem as estruturas esperadas (indices e tabela `exports`).
A cobertura funcional de `alembic upgrade head` fica por conta do CI.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"
MIGRATION_EXPORTS_PATH = VERSIONS_DIR / "0017_exports.py"
MIGRATION_EXECUTIONS_INDEX_PATH = (
    VERSIONS_DIR / "0017_executions_listing_index.py"
)


def _load_migration_source(path: Path) -> str:
    assert path.exists(), f"Migration ausente: {path}"
    return path.read_text(encoding="utf-8")


def _import_module(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_exports_migration_module_is_importable() -> None:
    module = _import_module(MIGRATION_EXPORTS_PATH, "migration_0017_exports")
    assert module.revision == "0017_exports"
    assert module.down_revision == "0016_merge_0015_heads"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_executions_index_migration_module_is_importable() -> None:
    module = _import_module(
        MIGRATION_EXECUTIONS_INDEX_PATH,
        "migration_0017_executions_listing_index",
    )
    assert module.revision == "0017_executions_listing_index"
    assert module.down_revision == "0016_merge_0015_heads"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_exports_migration_mentions_core_fields() -> None:
    src = _load_migration_source(MIGRATION_EXPORTS_PATH)
    assert '"exports"' in src
    for col in (
        "tenant_id",
        "company_id",
        "requested_by_user_id",
        "kind",
        "period_start",
        "period_end",
        "status",
        "file_id",
        "items_count",
        "total_bytes",
        "error_code",
        "error_message",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    ):
        assert f'"{col}"' in src, col

    assert "ck_exports_kind" in src
    assert "ck_exports_status" in src
    assert "ck_exports_period_order" in src
    assert "ck_exports_counters_nonneg" in src
    assert "'zip_xml'" in src
    assert "ENABLE ROW LEVEL SECURITY" in src
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "exports_isolation" in src
    assert "app.current_tenant" in src
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON exports TO app_user" in src


def test_migration_creates_two_indices_on_executions() -> None:
    src = _load_migration_source(MIGRATION_EXECUTIONS_INDEX_PATH)
    assert "ix_executions_tenant_started" in src
    assert "ix_executions_tenant_status_started" in src
    assert "started_at DESC NULLS LAST" in src
    assert '"executions"' in src or "'executions'" in src
    assert "create_index" in src


def test_exports_migration_has_matching_downgrade() -> None:
    src = _load_migration_source(MIGRATION_EXPORTS_PATH)
    assert "DROP POLICY IF EXISTS exports_isolation" in src
    assert 'drop_table("exports")' in src
    assert 'drop_index("ix_exports_tenant_created"' in src
    assert 'drop_index("ix_exports_tenant_company"' in src
    assert 'drop_index("ix_exports_inflight"' in src


def test_exports_indices_include_partial_inflight() -> None:
    src = _load_migration_source(MIGRATION_EXPORTS_PATH)
    assert "ix_exports_inflight" in src
    assert "status IN ('queued','running')" in src
    assert "drop_index" in src


def test_executions_index_migration_has_matching_downgrade() -> None:
    src = _load_migration_source(MIGRATION_EXECUTIONS_INDEX_PATH)
    assert '"ix_executions_tenant_status_started", table_name="executions"' in src
    assert 'drop_index("ix_executions_tenant_started", table_name="executions")' in src
