"""Testes estaticos da migration 0011_files (DATA-05 parte 1/4).

Nao conecta ao Postgres: valida estrutura do arquivo (tabela, colunas,
RLS, politica, GUC, grants, downgrade e merge de heads). Validacao
funcional (`alembic upgrade head` + RLS) e manual e esta no README.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0011_files.py"
)


def _load_migration_source() -> str:
    assert MIGRATION_PATH.exists(), f"Migration ausente: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_module_is_importable() -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_0011_files", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "0011_files"
    # Merge explicito dos dois heads anteriores.
    assert module.down_revision == (
        "0003_company_credentials",
        "0010_auth_refresh_tokens",
    )
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_mentions_core_fields() -> None:
    src = _load_migration_source()
    assert '"files"' in src
    for col in (
        "tenant_id",
        "kind",
        "object_key",
        "bytes",
        "checksum_sha256",
        "source_execution_id",
        "expires_at",
        "created_at",
        "updated_at",
    ):
        assert f'"{col}"' in src, col
    # Enum de kind + checksum hex + bytes >= 0.
    assert "ck_files_kind" in src
    assert "ck_files_checksum_sha256_hex" in src
    assert "ck_files_bytes_nonneg" in src
    assert "uq_files_tenant_object_key" in src
    # storage_tier NAO deve ser uma coluna (ADR-003: sem tiers).
    # (Mencoes em docstring/comentario explicando a decisao sao OK.)
    assert '"storage_tier"' not in src
    assert "'storage_tier'" not in src
    # RLS + policy + GUC.
    assert "ENABLE ROW LEVEL SECURITY" in src
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "files_isolation" in src
    assert "app.current_tenant" in src
    # Grants.
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON files TO app_user" in src


def test_migration_has_matching_downgrade() -> None:
    src = _load_migration_source()
    assert "DROP POLICY IF EXISTS files_isolation" in src
    assert 'drop_table("files")' in src
    assert 'drop_index("ix_files_tenant_id"' in src
    assert 'drop_index("ix_files_expires_at"' in src
    assert 'drop_index("ix_files_source_execution_id"' in src
