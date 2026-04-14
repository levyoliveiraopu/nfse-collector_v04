"""Testes estaticos da migration 0014_plans_subscriptions (DATA-05 parte 4/4)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0014_plans_subscriptions.py"
)


def _load_migration_source() -> str:
    assert MIGRATION_PATH.exists(), f"Migration ausente: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_module_is_importable() -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_0014_plans_subscriptions", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "0014_plans_subscriptions"
    assert module.down_revision == "0013_audit_logs"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_creates_plans_and_subscriptions() -> None:
    src = _load_migration_source()
    # plans (catalogo global).
    assert '"plans"' in src
    for col in ("code", "name", "limits", "price_cents", "active"):
        assert f'"{col}"' in src, col
    assert "ck_plans_price_nonneg" in src
    assert "ck_plans_code_format" in src
    # plans nao tem RLS; concede apenas SELECT a app_user.
    assert "GRANT SELECT ON plans TO app_user" in src
    # subscriptions (por tenant).
    assert '"subscriptions"' in src
    for col in (
        "tenant_id",
        "plan_id",
        "status",
        "current_period_start",
        "current_period_end",
        "gateway",
        "gateway_customer_id",
        "gateway_subscription_id",
    ):
        assert f'"{col}"' in src, col
    assert "uq_subscriptions_tenant_id" in src
    assert "ck_subscriptions_status" in src
    # RLS apenas em subscriptions.
    assert "subscriptions_isolation" in src
    assert "app.current_tenant" in src
    assert (
        "GRANT SELECT, INSERT, UPDATE, DELETE ON subscriptions TO app_user"
        in src
    )


def test_migration_promotes_tenants_plan_id_fk() -> None:
    src = _load_migration_source()
    # Promocao tenants.plan_id -> plans.code (conforme DATA-01).
    assert "fk_tenants_plan" in src
    assert "plans" in src


def test_migration_has_matching_downgrade() -> None:
    src = _load_migration_source()
    assert "DROP POLICY IF EXISTS subscriptions_isolation" in src
    assert 'drop_table("subscriptions")' in src
    assert 'drop_constraint("fk_tenants_plan"' in src
    assert 'drop_table("plans")' in src
