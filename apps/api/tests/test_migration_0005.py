"""Testes estaticos da migration 0005_execution_items (DATA-03 parte 2/2).

Nao se conectam ao Postgres: validam que a migration existe, pode ser
importada e contem os elementos chave (tabela, colunas, FK composta
para `executions`, CHECK de status, CHECK de formato de CNPJ emitente,
indices `(execution_id)` e `(tenant_id, data_emissao)`, indice unico
parcial `(tenant_id, chave_nfse) WHERE chave_nfse IS NOT NULL`, RLS,
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
    / "0005_execution_items.py"
)


def _load_migration_source() -> str:
    assert MIGRATION_PATH.exists(), f"Migration ausente: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_module_is_importable() -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_0005_execution_items", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "0005_execution_items"
    assert module.down_revision == "0004_executions"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_mentions_core_entities() -> None:
    src = _load_migration_source()
    # Tabela.
    assert '"execution_items"' in src or "'execution_items'" in src
    # Colunas exigidas pelo ticket.
    for col in (
        "execution_id",
        "tenant_id",
        "nsu",
        "chave_nfse",
        "cnpj_emitente",
        "data_emissao",
        "valor",
        "xml_object_key",
        "status",
        "error_code",
        "error_message",
        "created_at",
        "updated_at",
    ):
        assert col in src, col
    # FK composta (tenant_id, execution_id) -> executions(tenant_id, id).
    assert "fk_execution_items_tenant_execution" in src
    assert '"executions.tenant_id"' in src or "'executions.tenant_id'" in src
    assert '"executions.id"' in src or "'executions.id'" in src
    # FK para tenants.
    assert "tenants.id" in src
    # CHECKs.
    assert "ck_execution_items_status" in src
    assert "ck_execution_items_cnpj_emitente_format" in src
    # Indices.
    assert "ix_execution_items_execution_id" in src
    assert "ix_execution_items_tenant_data_emissao" in src
    # Unique parcial.
    assert "uq_execution_items_tenant_chave" in src
    assert "postgresql_where" in src
    assert "chave_nfse IS NOT NULL" in src
    # RLS + GUC.
    assert "ENABLE ROW LEVEL SECURITY" in src
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "app.current_tenant" in src
    assert "execution_items_isolation" in src
    # Grants.
    assert (
        "GRANT SELECT, INSERT, UPDATE, DELETE ON execution_items TO app_user"
        in src
    )


def test_migration_has_matching_downgrade() -> None:
    src = _load_migration_source()
    assert "DROP POLICY IF EXISTS execution_items_isolation" in src
    assert 'drop_table("execution_items")' in src
    for idx in (
        "uq_execution_items_tenant_chave",
        "ix_execution_items_tenant_data_emissao",
        "ix_execution_items_execution_id",
    ):
        assert f'"{idx}"' in src, idx
    assert "drop_index" in src
