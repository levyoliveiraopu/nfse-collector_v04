"""Testes estaticos da migration 0015_companies_deleted_at (API-05).

Valida sem conexao ao Postgres que a migration:
- encadeia corretamente (revises 0014_plans_subscriptions).
- adiciona `deleted_at`.
- substitui o UNIQUE total de `(tenant_id, cnpj)` por indice UNIQUE
  parcial `WHERE deleted_at IS NULL`.
- cria indice parcial de listagem.
- tem downgrade simetrico.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0015_companies_deleted_at.py"
)


def _load_source() -> str:
    assert MIGRATION_PATH.exists(), f"Migration ausente: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_importavel_e_encadeada() -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_0015_companies_deleted_at", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "0015_companies_deleted_at"
    assert module.down_revision == "0014_plans_subscriptions"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_upgrade_adiciona_coluna_deleted_at() -> None:
    src = _load_source()
    assert "add_column" in src
    assert "deleted_at" in src
    assert "TIMESTAMP(timezone=True)" in src


def test_upgrade_troca_unique_por_indice_parcial() -> None:
    src = _load_source()
    assert "drop_constraint" in src and "uq_companies_tenant_cnpj" in src
    assert "CREATE UNIQUE INDEX uq_companies_tenant_cnpj_live" in src
    assert "WHERE deleted_at IS NULL" in src


def test_upgrade_cria_indice_parcial_de_listagem() -> None:
    src = _load_source()
    assert "ix_companies_tenant_live" in src


def test_downgrade_simetrico() -> None:
    src = _load_source()
    assert "DROP INDEX IF EXISTS ix_companies_tenant_live" in src
    assert "DROP INDEX IF EXISTS uq_companies_tenant_cnpj_live" in src
    assert "drop_column" in src and "deleted_at" in src
    assert "create_unique_constraint" in src
