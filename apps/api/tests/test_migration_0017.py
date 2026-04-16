"""Testes estaticos da migration 0017_exports (API-15).

Nao conecta ao Postgres: valida estrutura do arquivo (tabela, colunas,
checks, RLS, politica, GUC, grants, downgrade). Cobertura funcional
via `alembic upgrade head` fica por conta do CI job `test-rls`.
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
    / "0017_exports.py"
    / "0017_executions_listing_index.py"
)


def _load_migration_source() -> str:
    assert MIGRATION_PATH.exists(), f"Migration ausente: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_module_is_importable() -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_0017_exports", MIGRATION_PATH
        "migration_0017_executions_listing_index", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "0017_exports"
    assert module.revision == "0017_executions_listing_index"
    assert module.down_revision == "0016_merge_0015_heads"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_mentions_core_fields() -> None:
    src = _load_migration_source()
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
    # CHECKs criticos.
    assert "ck_exports_kind" in src
    assert "ck_exports_status" in src
    assert "ck_exports_period_order" in src
    assert "ck_exports_counters_nonneg" in src
    # Enum kind hoje so `zip_xml` (excel_consolidated adiado — ver schemas.py).
    assert "'zip_xml'" in src
    # RLS + policy + GUC.
    assert "ENABLE ROW LEVEL SECURITY" in src
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "exports_isolation" in src
    assert "app.current_tenant" in src
    # Grants DML para app_user.
    assert (
        "GRANT SELECT, INSERT, UPDATE, DELETE ON exports TO app_user"
        in src
    )
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
    assert "DROP POLICY IF EXISTS exports_isolation" in src
    assert 'drop_table("exports")' in src
    assert 'drop_index("ix_exports_tenant_created"' in src
    assert 'drop_index("ix_exports_tenant_company"' in src
    assert 'drop_index("ix_exports_inflight"' in src


def test_indices_incluem_parcial_de_inflight() -> None:
    src = _load_migration_source()
    # Parcial para o worker/admin acharem exports em voo.
    assert "ix_exports_inflight" in src
    assert "status IN ('queued','running')" in src
    assert "drop_index" in src
    for idx in (
        "ix_executions_tenant_status_started",
        "ix_executions_tenant_started",
    ):
        assert idx in src, idx
