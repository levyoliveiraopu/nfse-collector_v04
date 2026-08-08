"""Contrato da migration de metricas anonimizadas da ajuda."""

from pathlib import Path


def test_migration_0020_has_rls_checks_and_no_user_id() -> None:
    path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0020_help_metrics_daily.py"
    )
    source = path.read_text(encoding="utf-8")

    assert 'revision: str = "0020_help_metrics_daily"' in source
    assert 'down_revision: Union[str, None] = "0019_export_excel_nfse"' in source
    assert "CREATE POLICY help_metrics_daily_isolation" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "ck_help_metrics_daily_event_type" in source
    assert "ck_help_metrics_daily_count" in source
    assert "user_id" not in source
