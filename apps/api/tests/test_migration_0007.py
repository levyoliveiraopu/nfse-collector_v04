"""Testes estaticos da migration 0007_reprocess_jobs (DATA-04 parte 2/3).

Nao se conectam ao Postgres: validam que a migration existe, pode ser
importada e contem os elementos chave (tabela, FKs, colunas jsonb/
text[], CHECK de status, RLS, politica, GUC, grants, downgrade
simetrico).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0007_reprocess_jobs.py"
)


def _load_migration_source() -> str:
    assert MIGRATION_PATH.exists(), f"Migration ausente: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_module_is_importable() -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_0007_reprocess_jobs", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "0007_reprocess_jobs"
    assert module.down_revision == "0006_occurrences"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_mentions_core_entities() -> None:
    src = _load_migration_source()
    # Tabela.
    assert '"reprocess_jobs"' in src or "'reprocess_jobs'" in src
    # Colunas exigidas pelo ticket.
    for col in (
        "tenant_id",
        "created_by_user_id",
        "scope",
        "status",
        "result_execution_ids",
    ):
        assert col in src, col
    # FKs.
    assert "tenants.id" in src
    assert "users.id" in src
    # JSONB + text[].
    assert "JSONB" in src
    assert "ARRAY" in src
    # CHECK de status.
    assert "ck_reprocess_jobs_status" in src
    # Indices.
    for idx in (
        "ix_reprocess_jobs_tenant_id",
        "ix_reprocess_jobs_tenant_status",
        "ix_reprocess_jobs_tenant_created",
    ):
        assert idx in src, idx
    # RLS + GUC.
    assert "ENABLE ROW LEVEL SECURITY" in src
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "app.current_tenant" in src
    assert "reprocess_jobs_isolation" in src
    # Grants.
    assert (
        "GRANT SELECT, INSERT, UPDATE, DELETE ON reprocess_jobs TO app_user"
        in src
    )


def test_migration_has_matching_downgrade() -> None:
    src = _load_migration_source()
    assert "DROP POLICY IF EXISTS reprocess_jobs_isolation" in src
    assert 'drop_table("reprocess_jobs")' in src
    for idx in (
        "ix_reprocess_jobs_tenant_created",
        "ix_reprocess_jobs_tenant_status",
        "ix_reprocess_jobs_tenant_id",
    ):
        assert f'"{idx}"' in src, idx
        assert "drop_index" in src
