"""Testes estaticos da migration 0004_executions (DATA-03 parte 1/2).

Nao se conectam ao Postgres: validam que a migration existe, pode ser
importada e contem os elementos chave (tabela, colunas, FK composta
para `companies`, CHECKs de trigger/status/periodo/soma, indice
composto `(tenant_id, company_id, started_at DESC)`, RLS, politica,
GUC, grants, downgrade simetrico). A validacao funcional (`alembic
upgrade head` / `downgrade -1` + RLS cross-tenant + EXPLAIN da query
de listagem por periodo) e manual e esta documentada em
`apps/api/README.md`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0004_executions.py"
)


def _load_migration_source() -> str:
    assert MIGRATION_PATH.exists(), f"Migration ausente: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_module_is_importable() -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_0004_executions", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "0004_executions"
    assert module.down_revision == "0003_company_credentials"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_mentions_core_entities() -> None:
    src = _load_migration_source()
    # Tabela.
    assert '"executions"' in src or "'executions'" in src
    # Colunas exigidas pelo ticket.
    for col in (
        "tenant_id",
        "company_id",
        "trigger",
        "triggered_by_user_id",
        "period_start",
        "period_end",
        "status",
        "started_at",
        "finished_at",
        "nsu_from",
        "nsu_to",
        "items_total",
        "items_ok",
        "items_fail",
        "error_summary",
        "created_at",
        "updated_at",
    ):
        assert col in src, col
    # FK composta (tenant_id, company_id) -> companies(tenant_id, id).
    assert "fk_executions_tenant_company" in src
    assert '"companies.tenant_id"' in src or "'companies.tenant_id'" in src
    assert '"companies.id"' in src or "'companies.id'" in src
    # FK para tenants e users.
    assert "tenants.id" in src
    assert "users.id" in src
    # UNIQUE(tenant_id, id) habilita FK composta em execution_items.
    assert "uq_executions_tenant_id_id" in src
    # CHECKs.
    assert "ck_executions_trigger" in src
    assert "ck_executions_status" in src
    assert "ck_executions_period_order" in src
    assert "ck_executions_items_sum" in src
    # Indice composto (tenant_id, company_id, started_at DESC).
    assert "ix_executions_tenant_company_started" in src
    assert "started_at DESC" in src
    # RLS + GUC.
    assert "ENABLE ROW LEVEL SECURITY" in src
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "app.current_tenant" in src
    assert "executions_isolation" in src
    # Grants.
    assert (
        "GRANT SELECT, INSERT, UPDATE, DELETE ON executions TO app_user" in src
    )


def test_migration_has_matching_downgrade() -> None:
    src = _load_migration_source()
    assert "DROP POLICY IF EXISTS executions_isolation" in src
    assert 'drop_table("executions")' in src
    for idx in (
        "ix_executions_tenant_company_started",
        "ix_executions_tenant_id",
    ):
        assert f'"{idx}"' in src, idx
    assert "drop_index" in src
