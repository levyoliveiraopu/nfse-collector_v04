"""Testes de integracao do fluxo de auth (API-02).

Requerem um Postgres real com o schema das migrations 0001 e 0010
aplicadas. Sao pulados se `TEST_DATABASE_URL` nao estiver setada —
o objetivo e manter o CI rapido e deterministico, delegando o E2E
para ambientes de dev/staging.

Como rodar localmente:

    export TEST_DATABASE_URL="postgresql+psycopg://app_admin:***@localhost:5432/nfse_test"
    alembic -x url="$TEST_DATABASE_URL" upgrade head
    pytest apps/api/tests/test_auth_routes_integration.py -v

Nota: o banco apontado e TRUNCADO antes de cada teste. Nunca aponte
para um banco de producao/staging.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL nao definida — pulando integracao Postgres.",
)


@pytest.fixture()
def client():
    # Importacoes adiadas para evitar custo de setup quando o modulo e pulado.
    os.environ["API_DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ.setdefault("API_JWT_SECRET", "integration-test-secret")
    os.environ.setdefault("API_ENVIRONMENT", "development")
    os.environ.setdefault("API_LOGIN_RATE_LIMIT", "1000/minute")

    from api.config import get_settings
    from api.db import get_admin_session, reset_engine_for_tests
    from api.main import create_app
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    get_settings.cache_clear()  # type: ignore[attr-defined]
    reset_engine_for_tests()

    with get_admin_session() as session:
        session.execute(text("TRUNCATE refresh_tokens, tenant_users, users, tenants CASCADE"))

    app = create_app()
    with TestClient(app) as client:
        yield client

    reset_engine_for_tests()


def _signup(client, *, slug: str = "acme", email: str = "ana@acme.test") -> dict:
    resp = client.post(
        "/auth/signup",
        json={
            "tenant_name": "Acme Contabil",
            "tenant_slug": slug,
            "name": "Ana Silva",
            "email": email,
            "password": "super-senha-123",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_signup_login_refresh_logout_flow(client) -> None:
    body = _signup(client)
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["role"] == "owner"

    login = client.post(
        "/auth/login",
        json={"email": "ana@acme.test", "password": "super-senha-123"},
    )
    assert login.status_code == 200, login.text
    login_body = login.json()
    assert login_body["access_token"] != body["access_token"]

    refresh = client.post(
        "/auth/refresh",
        json={"refresh_token": login_body["refresh_token"]},
    )
    assert refresh.status_code == 200, refresh.text
    new_refresh = refresh.json()["refresh_token"]
    assert new_refresh != login_body["refresh_token"]

    # Refresh antigo nao pode mais ser usado (rotacao).
    reused = client.post(
        "/auth/refresh",
        json={"refresh_token": login_body["refresh_token"]},
    )
    assert reused.status_code == 401

    # Logout revoga o refresh corrente.
    logout = client.post(
        "/auth/logout", json={"refresh_token": new_refresh}
    )
    assert logout.status_code == 200
    assert logout.json()["revoked"] is True

    # Apos logout o refresh nao e mais valido.
    after = client.post(
        "/auth/refresh",
        json={"refresh_token": new_refresh},
    )
    assert after.status_code == 401


def test_login_wrong_password_is_generic_401(client) -> None:
    _signup(client)
    resp = client.post(
        "/auth/login",
        json={"email": "ana@acme.test", "password": "errada"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "credenciais invalidas"


def test_signup_conflict_on_duplicate_slug(client) -> None:
    _signup(client, slug="acme", email="a@acme.test")
    resp = client.post(
        "/auth/signup",
        json={
            "tenant_name": "Outra",
            "tenant_slug": "acme",
            "name": "Beto",
            "email": "b@acme.test",
            "password": "outra-senha-456",
        },
    )
    assert resp.status_code == 409


def test_refresh_reuse_detection_invalidates_chain(client) -> None:
    body = _signup(client, slug="chain", email="chain@acme.test")
    r1 = client.post(
        "/auth/refresh", json={"refresh_token": body["refresh_token"]}
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/auth/refresh", json={"refresh_token": r1.json()["refresh_token"]}
    )
    assert r2.status_code == 200

    # Reuso do primeiro refresh (ja revogado) deve invalidar toda a cadeia.
    reuse = client.post(
        "/auth/refresh", json={"refresh_token": body["refresh_token"]}
    )
    assert reuse.status_code == 401

    # Apos a deteccao, o refresh mais recente tambem deve estar inutilizavel.
    follow = client.post(
        "/auth/refresh", json={"refresh_token": r2.json()["refresh_token"]}
    )
    assert follow.status_code == 401
