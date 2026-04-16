"""Testes estaticos da migration 0017_executions_listing_index (API-08).

Nao se conectam ao Postgres: validam que a migration existe, pode ser
importada e contem os 2 indices auxiliares para `executions` exigidos
pelo DoD do ticket ("query valida com EXPLAIN (usa indice)").
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0017_executions_listing_index.py"
)


def _load_migration_source() -> str:
    assert MIGRATION_PATH.exists(), f"Migration ausente: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_module_is_importable() -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_0017_executions_listing_index", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "0017_executions_listing_index"
    assert module.down_revision == "0016_merge_0015_heads"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_creates_two_indices_on_executions() -> None:
    src = _load_migration_source()
    # Indices exigidos.
    assert "ix_executions_tenant_started" in src
    assert "ix_executions_tenant_status_started" in src
    # Cobertura: tenant + started_at DESC (NULLS LAST) + tiebreaker id.
    assert "started_at DESC NULLS LAST" in src
    assert '"executions"' in src or "'executions'" in src
    assert "create_index" in src


def test_migration_has_matching_downgrade() -> None:
    src = _load_migration_source()
    assert "drop_index" in src
    for idx in (
        "ix_executions_tenant_status_started",
        "ix_executions_tenant_started",
    ):
        assert idx in src, idx
