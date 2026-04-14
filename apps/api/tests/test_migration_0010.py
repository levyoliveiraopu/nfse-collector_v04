"""Testes estaticos da migration 0010_auth_refresh_tokens (API-02).

No mesmo espirito de test_migration_0001: nao conecta ao Postgres;
valida que o arquivo e importavel e contem os elementos chave
(colunas, RLS, politica, indices, grants, downgrade).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0010_auth_refresh_tokens.py"
)


def _load_migration_source() -> str:
    assert MIGRATION_PATH.exists(), f"Migration ausente: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_module_is_importable() -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_0010_auth_refresh_tokens", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "0010_auth_refresh_tokens"
    assert module.down_revision == "0001_initial_identity"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_mentions_core_fields() -> None:
    src = _load_migration_source()
    # Tabela e colunas essenciais.
    assert '"refresh_tokens"' in src
    for col in (
        "tenant_id",
        "user_id",
        "token_hash",
        "issued_at",
        "expires_at",
        "revoked_at",
        "replaced_by",
        "user_agent",
    ):
        assert f'"{col}"' in src, col
    # Unique no hash e indice em expires_at com filtro partial.
    assert "uq_refresh_tokens_token_hash" in src
    assert "ix_refresh_tokens_user_active" in src
    assert "revoked_at IS NULL" in src
    # RLS + policy + GUC.
    assert "ENABLE ROW LEVEL SECURITY" in src
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "refresh_tokens_isolation" in src
    assert "app.current_tenant" in src
    # Grants para app_user.
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON refresh_tokens TO app_user" in src


def test_migration_has_matching_downgrade() -> None:
    src = _load_migration_source()
    assert "DROP POLICY IF EXISTS refresh_tokens_isolation" in src
    assert 'drop_table("refresh_tokens")' in src
    assert 'drop_index("ix_refresh_tokens_user_active"' in src
    assert 'drop_index("ix_refresh_tokens_tenant_id"' in src
    assert 'drop_index("ix_refresh_tokens_user_id"' in src
