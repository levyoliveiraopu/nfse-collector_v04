"""Contrato da migration que habilita o export Excel."""

from pathlib import Path


def test_migration_0019_extends_export_kind() -> None:
    path = Path(__file__).parents[1] / "alembic" / "versions" / "0019_export_excel_nfse.py"
    source = path.read_text(encoding="utf-8")
    assert 'revision: str = "0019_export_excel_nfse"' in source
    assert 'down_revision: Union[str, None] = "0018_merge_0017_heads"' in source
    assert "kind IN ('zip_xml','excel_nfse')" in source
