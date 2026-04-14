"""Testes estaticos da migration 0003_company_credentials (DATA-02 parte 2/2).

Nao se conectam ao Postgres: validam que a migration existe, pode ser
importada e contem os elementos chave (tabela, FKs, indice em
`cert_not_after`, CHECK de type/status, RLS, politica, GUC, grants,
downgrade simetrico). A validacao funcional (`alembic upgrade head` /
`downgrade -1` + RLS cross-tenant) e manual e esta documentada em
`apps/api/README.md`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0003_company_credentials.py"
)


def _load_migration_source() -> str:
    assert MIGRATION_PATH.exists(), f"Migration ausente: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_module_is_importable() -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_0003_company_credentials", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "0003_company_credentials"
    assert module.down_revision == "0002_companies"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_mentions_core_entities() -> None:
    src = _load_migration_source()
    # Tabela.
    assert '"company_credentials"' in src or "'company_credentials'" in src
    # Colunas exigidas pelo ticket.
    for col in (
        "tenant_id",
        "company_id",
        "type",
        "pfx_object_key",
        "pfx_password_ciphertext",
        "cert_fingerprint",
        "cert_not_before",
        "cert_not_after",
        "status",
        "last_used_at",
        "last_tested_at",
        "created_at",
        "updated_at",
    ):
        assert col in src, col
    # FK composta (tenant_id, company_id) -> companies(tenant_id, id).
    assert "fk_company_credentials_tenant_company" in src
    assert '"companies.tenant_id"' in src or "'companies.tenant_id'" in src
    assert '"companies.id"' in src or "'companies.id'" in src
    # FK para tenants (tenant_id isolado).
    assert "tenants.id" in src
    # CHECK de type e status.
    assert "ck_company_credentials_type" in src
    assert "ck_company_credentials_status" in src
    # Indice em cert_not_after (alerta de vencimento).
    assert "ix_company_credentials_cert_not_after" in src
    # RLS + GUC.
    assert "ENABLE ROW LEVEL SECURITY" in src
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "app.current_tenant" in src
    assert "company_credentials_isolation" in src
    # Grants.
    assert (
        "GRANT SELECT, INSERT, UPDATE, DELETE ON company_credentials TO app_user"
        in src
    )


def test_migration_has_matching_downgrade() -> None:
    src = _load_migration_source()
    assert "DROP POLICY IF EXISTS company_credentials_isolation" in src
    assert 'drop_table("company_credentials")' in src
    # `drop_index` pode estar quebrado em multiplas linhas — usamos
    # `op.drop_index(\n    "..."` como padrao frouxo.
    for idx in (
        "ix_company_credentials_cert_not_after",
        "ix_company_credentials_company_id",
        "ix_company_credentials_tenant_id",
    ):
        assert f'"{idx}"' in src, idx
        assert "drop_index" in src
