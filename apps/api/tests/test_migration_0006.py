"""Testes estaticos da migration 0006_occurrences (DATA-04 parte 1/3).

Nao se conectam ao Postgres: validam que a migration existe, pode ser
importada e contem os elementos chave (tabela, FKs compostas, indices,
CHECKs, RLS, politica, GUC, grants, downgrade simetrico). A validacao
funcional (`alembic upgrade head` / `downgrade -1` + RLS cross-tenant)
e manual e esta documentada em `apps/api/README.md`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0006_occurrences.py"
)


def _load_migration_source() -> str:
    assert MIGRATION_PATH.exists(), f"Migration ausente: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_module_is_importable() -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_0006_occurrences", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "0006_occurrences"
    assert module.down_revision == "0005_execution_items"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_mentions_core_entities() -> None:
    src = _load_migration_source()
    # Tabela.
    assert '"occurrences"' in src or "'occurrences'" in src
    # Colunas exigidas pelo ticket.
    for col in (
        "tenant_id",
        "company_id",
        "execution_id",
        "severity",
        "code",
        "title",
        "detail",
        "status",
        "assignee_user_id",
        "first_seen_at",
        "last_seen_at",
        "resolved_at",
    ):
        assert col in src, col
    # FK para tenants.
    assert "tenants.id" in src
    # FK composta (tenant_id, company_id) -> companies(tenant_id, id).
    assert "fk_occurrences_tenant_company" in src
    assert '"companies.tenant_id"' in src or "'companies.tenant_id'" in src
    assert '"companies.id"' in src or "'companies.id'" in src
    # FK composta (tenant_id, execution_id) -> executions(tenant_id, id).
    assert "fk_occurrences_tenant_execution" in src
    assert '"executions.tenant_id"' in src or "'executions.tenant_id'" in src
    assert '"executions.id"' in src or "'executions.id'" in src
    # FK para users (assignee).
    assert "users.id" in src
    # CHECKs.
    assert "ck_occurrences_severity" in src
    assert "ck_occurrences_status" in src
    assert "ck_occurrences_seen_order" in src
    # Indices.
    for idx in (
        "ix_occurrences_tenant_id",
        "ix_occurrences_tenant_status",
        "ix_occurrences_tenant_company",
        "ix_occurrences_execution_id",
    ):
        assert idx in src, idx
    # RLS + GUC.
    assert "ENABLE ROW LEVEL SECURITY" in src
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "app.current_tenant" in src
    assert "occurrences_isolation" in src
    # Grants.
    assert (
        "GRANT SELECT, INSERT, UPDATE, DELETE ON occurrences TO app_user" in src
    )


def test_migration_has_matching_downgrade() -> None:
    src = _load_migration_source()
    assert "DROP POLICY IF EXISTS occurrences_isolation" in src
    assert 'drop_table("occurrences")' in src
    for idx in (
        "ix_occurrences_execution_id",
        "ix_occurrences_tenant_company",
        "ix_occurrences_tenant_status",
        "ix_occurrences_tenant_id",
    ):
        assert f'"{idx}"' in src, idx
        assert "drop_index" in src
