"""Testes estaticos da migration 0002_companies (DATA-02 parte 1/2).

Nao se conectam ao Postgres: validam que a migration existe, pode ser
importada e contem os elementos chave (tabela, FK, unicos, CHECK, RLS,
politica, GUC, grants, downgrade simetrico). A validacao funcional
(`alembic upgrade head` / `downgrade -1` + RLS cross-tenant) e manual
e esta documentada em `apps/api/README.md`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0002_companies.py"
)


def _load_migration_source() -> str:
    assert MIGRATION_PATH.exists(), f"Migration ausente: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_module_is_importable() -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_0002_companies", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "0002_companies"
    assert module.down_revision == "0001_initial_identity"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_mentions_core_entities() -> None:
    src = _load_migration_source()
    # Tabela.
    assert '"companies"' in src or "'companies'" in src
    # Colunas exigidas pelo ticket.
    for col in (
        "tenant_id",
        "cnpj",
        "razao_social",
        "nome_fantasia",
        "municipio_ibge",
        "uf",
        "status",
        "last_nsu",
        "last_success_at",
        "portal_provider",
        "notes",
        "created_at",
        "updated_at",
    ):
        assert col in src, col
    # Unicos e constraints.
    assert "uq_companies_tenant_cnpj" in src
    assert "uq_companies_tenant_id_id" in src
    assert "ck_companies_status" in src
    assert "ck_companies_cnpj_format" in src
    # FK para tenants.
    assert "tenants.id" in src
    # RLS + GUC.
    assert "ENABLE ROW LEVEL SECURITY" in src
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "app.current_tenant" in src
    assert "companies_isolation" in src
    # Grants.
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON companies TO app_user" in src


def test_migration_has_matching_downgrade() -> None:
    src = _load_migration_source()
    assert "DROP POLICY IF EXISTS companies_isolation" in src
    assert 'drop_table("companies")' in src
    assert 'drop_index("ix_companies_tenant_id"' in src
