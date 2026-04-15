"""Testes do seed de dev (DATA-07).

Duas camadas:

1. **Estatica** (sem DB): valida constantes, formato dos plans, resolucao
   da senha admin (fallback em dev, abort em prod), idempotencia das
   funcoes de upsert via mock de `Session`.

2. **Integracao** (requer `TEST_DATABASE_URL` com `alembic upgrade head`):
   roda `run_seed()` duas vezes e confere que (a) nao duplica linhas,
   (b) deixa o banco num estado consistente (tenant + user + membership
   criados com os atributos esperados). Pulado quando a env nao esta
   setada — mesmo padrao de `test_audit_logs_bulk.py`.
"""

from __future__ import annotations

import json
import os
import uuid
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Estatica
# ---------------------------------------------------------------------------

def test_plans_constant_has_expected_codes() -> None:
    from scripts.seed import PLANS

    codes = [p.code for p in PLANS]
    assert codes == ["starter", "pro", "scale"]


def test_plans_limits_are_json_serializable_dicts() -> None:
    from scripts.seed import PLANS

    for plan in PLANS:
        assert isinstance(plan.limits, dict)
        # Precisa serializar para jsonb sem levantar.
        json.dumps(plan.limits)
        # Cada plano tem pelo menos companies/executions/users.
        assert {"companies", "executions_per_month", "users"} <= plan.limits.keys()
        assert plan.price_cents >= 0


def test_demo_constants() -> None:
    from scripts.seed import (
        DEMO_TENANT_PLAN,
        DEMO_TENANT_SLUG,
        DEMO_USER_EMAIL,
        DEMO_USER_ROLE,
    )

    assert DEMO_TENANT_SLUG == "demo"
    assert DEMO_TENANT_PLAN == "pro"
    assert DEMO_USER_EMAIL == "admin@demo.local"
    assert DEMO_USER_ROLE == "owner"


def test_resolve_admin_password_prefers_env(monkeypatch) -> None:
    from scripts import seed

    monkeypatch.setenv("API_SEED_ADMIN_PASSWORD", "  supersecret  ")
    assert seed.resolve_admin_password() == "supersecret"


def test_resolve_admin_password_dev_fallback(monkeypatch) -> None:
    from api.config import get_settings
    from scripts import seed

    monkeypatch.delenv("API_SEED_ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("API_ENVIRONMENT", "development")
    get_settings.cache_clear()  # type: ignore[attr-defined]

    try:
        assert seed.resolve_admin_password() == seed._DEV_FALLBACK_PASSWORD
    finally:
        get_settings.cache_clear()  # type: ignore[attr-defined]


def test_resolve_admin_password_aborts_in_production(monkeypatch) -> None:
    from api.config import get_settings
    from scripts import seed

    monkeypatch.delenv("API_SEED_ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("API_ENVIRONMENT", "production")
    # Staging/prod exigem JWT_SECRET e KEK; basta valores nao vazios.
    monkeypatch.setenv("API_JWT_SECRET", "placeholder-for-validation")
    monkeypatch.setenv(
        "API_CREDENTIAL_KEK_B64",
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    )
    get_settings.cache_clear()  # type: ignore[attr-defined]

    try:
        with pytest.raises(SystemExit):
            seed.resolve_admin_password()
    finally:
        get_settings.cache_clear()  # type: ignore[attr-defined]


def test_upsert_plan_uses_on_conflict_do_update() -> None:
    from scripts.seed import PLANS, upsert_plan

    session = MagicMock()
    upsert_plan(session, PLANS[0])
    # Deve ter executado um INSERT ... ON CONFLICT (code) DO UPDATE.
    stmt_arg = session.execute.call_args.args[0]
    sql_text = str(stmt_arg)
    assert "INSERT INTO plans" in sql_text
    assert "ON CONFLICT (code) DO UPDATE" in sql_text


def test_upsert_user_uses_lower_email_conflict() -> None:
    from scripts.seed import upsert_user

    session = MagicMock()
    session.execute.return_value.one.return_value = (uuid.uuid4(),)
    upsert_user(
        session,
        email="admin@demo.local",
        name="Admin",
        password_hash="$argon2id$fake",
    )
    stmt_arg = session.execute.call_args.args[0]
    sql_text = str(stmt_arg)
    assert "ON CONFLICT ((LOWER(email))) DO UPDATE" in sql_text


def test_upsert_membership_conflict_on_composite_pk() -> None:
    from scripts.seed import upsert_membership

    session = MagicMock()
    upsert_membership(
        session,
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        role="owner",
    )
    stmt_arg = session.execute.call_args.args[0]
    sql_text = str(stmt_arg)
    assert "ON CONFLICT (tenant_id, user_id) DO UPDATE" in sql_text


# ---------------------------------------------------------------------------
# Integracao (DB real)
# ---------------------------------------------------------------------------

integration = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL nao definida — pulando integracao do seed.",
)


@pytest.fixture()
def clean_db():
    os.environ["API_DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ.setdefault("API_JWT_SECRET", "integration-test-secret")
    os.environ.setdefault("API_ENVIRONMENT", "development")
    os.environ.setdefault("API_SEED_ADMIN_PASSWORD", "seed-integration-pass")

    from api.config import get_settings
    from api.db import get_admin_session, reset_engine_for_tests
    from sqlalchemy import text

    get_settings.cache_clear()  # type: ignore[attr-defined]
    reset_engine_for_tests()

    with get_admin_session() as session:
        # Remove o tenant demo e plans previos para partir de estado
        # conhecido. CASCADE derruba tenant_users + subscriptions.
        session.execute(
            text("DELETE FROM tenants WHERE slug = 'demo'")
        )
        session.execute(
            text("DELETE FROM users WHERE LOWER(email) = LOWER('admin@demo.local')")
        )
        session.execute(
            text("DELETE FROM plans WHERE code IN ('starter','pro','scale')")
        )

    yield

    reset_engine_for_tests()


@integration
def test_run_seed_is_idempotent(clean_db) -> None:
    from sqlalchemy import text

    from api.db import get_admin_session
    from scripts.seed import run_seed

    run_seed()
    run_seed()

    with get_admin_session() as session:
        plans = session.execute(
            text(
                "SELECT code FROM plans WHERE code IN ('starter','pro','scale') "
                "ORDER BY code"
            )
        ).scalars().all()
        assert plans == ["pro", "scale", "starter"]

        tenant_count = session.execute(
            text("SELECT COUNT(*) FROM tenants WHERE slug = 'demo'")
        ).scalar_one()
        assert tenant_count == 1

        user_count = session.execute(
            text(
                "SELECT COUNT(*) FROM users WHERE LOWER(email) = "
                "LOWER('admin@demo.local')"
            )
        ).scalar_one()
        assert user_count == 1

        # Membership owner criada.
        role = session.execute(
            text(
                "SELECT tu.role FROM tenant_users tu "
                "JOIN tenants t ON t.id = tu.tenant_id "
                "JOIN users u ON u.id = tu.user_id "
                "WHERE t.slug = 'demo' "
                "AND LOWER(u.email) = LOWER('admin@demo.local')"
            )
        ).scalar_one()
        assert role == "owner"
