"""Testes estaticos da migration 0001_initial_identity (DATA-01).

Estes testes nao se conectam ao Postgres: validam que a migration existe,
pode ser importada como modulo Python e contem os elementos chave
(tabelas, roles, RLS, politicas, GUC). A validacao funcional
(`alembic upgrade head` / `downgrade -1`) e manual e esta documentada
em `apps/api/README.md` (Definition of Done do ticket).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0001_initial_identity.py"
)


def _load_migration_source() -> str:
    assert MIGRATION_PATH.exists(), f"Migration ausente: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_module_is_importable() -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_0001_initial_identity", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    # Executa o modulo top-level (define `revision`, `upgrade`, `downgrade`).
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "0001_initial_identity"
    assert module.down_revision is None
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_mentions_core_entities() -> None:
    src = _load_migration_source()
    # Extensoes e helpers.
    assert "pgcrypto" in src
    assert "gen_random_uuid" in src
    # Roles.
    assert "app_admin" in src
    assert "app_user" in src
    assert "BYPASSRLS" in src
    assert "NOBYPASSRLS" in src
    # Tabelas.
    for table in ("tenants", "users", "tenant_users"):
        assert f'"{table}"' in src or f"'{table}'" in src, table
    # RLS + GUC.
    assert "ENABLE ROW LEVEL SECURITY" in src
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "app.current_tenant" in src
    # Politicas nominais.
    assert "tenants_isolation" in src
    assert "tenant_users_isolation" in src


def test_migration_has_matching_downgrade() -> None:
    src = _load_migration_source()
    # Drops para reverter o estado inicial.
    assert "DROP POLICY IF EXISTS tenants_isolation" in src
    assert "DROP POLICY IF EXISTS tenant_users_isolation" in src
    assert 'drop_table("tenant_users")' in src
    assert 'drop_table("users")' in src
    assert 'drop_table("tenants")' in src
    assert "DROP ROLE IF EXISTS app_user" in src
    assert "DROP ROLE IF EXISTS app_admin" in src
