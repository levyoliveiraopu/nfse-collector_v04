"""Testes E2E do middleware de tenant (API-03).

Requerem Postgres real com as migrations 0001 e 0010 aplicadas. Pulam
silenciosamente se `TEST_DATABASE_URL` nao estiver setada (mesmo padrao
de `test_auth_routes_integration.py`).

Cobertura:
- Tenant A nao enxerga `tenant_users` do tenant B (RLS ativa).
- Conexao devolvida ao pool nao carrega GUC: request sem token apos
  request autenticada nao vaza linhas de tenants anteriores.
- Tenant com status `suspended` ou `canceled` recebe 403.
- `/auth/me` sem token -> 401; com token valido -> 200 com identidade.
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
        session.execute(
            text("TRUNCATE refresh_tokens, tenant_users, users, tenants CASCADE")
        )

    app = create_app()
    with TestClient(app) as c:
        yield c

    reset_engine_for_tests()


def _signup(client, *, slug: str, email: str) -> dict:
    resp = client.post(
        "/auth/signup",
        json={
            "tenant_name": slug.title(),
            "tenant_slug": slug,
            "name": f"User {slug}",
            "email": email,
            "password": "super-senha-123",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_me_requires_bearer_token(client) -> None:
    assert client.get("/auth/me").status_code == 401
    assert (
        client.get("/auth/me", headers={"Authorization": "Basic zzz"}).status_code
        == 401
    )
    assert (
        client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code
        == 401
    )


def test_me_returns_identity_for_valid_token(client) -> None:
    a = _signup(client, slug="acme", email="a@acme.test")
    resp = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {a['access_token']}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tenant_id"] == a["tenant_id"]
    assert body["user_id"] == a["user_id"]
    assert body["role"] == "owner"
    # Sob RLS o usuario so enxerga a propria associacao de tenant.
    assert body["memberships_visible"] == 1


def test_cross_tenant_isolation_via_me(client) -> None:
    a = _signup(client, slug="acme", email="a@acme.test")
    b = _signup(client, slug="beta", email="b@beta.test")

    me_a = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {a['access_token']}"}
    ).json()
    me_b = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {b['access_token']}"}
    ).json()

    assert me_a["tenant_id"] != me_b["tenant_id"]
    # Cada user so ve a propria associacao (1), nao a do outro (2).
    assert me_a["memberships_visible"] == 1
    assert me_b["memberships_visible"] == 1


def test_guc_does_not_leak_between_requests(client) -> None:
    """Apos uma request autenticada como tenant A, uma request nao
    autenticada (sem token) nao pode herdar a GUC no pool."""
    a = _signup(client, slug="acme", email="a@acme.test")
    # Exercita a conexao com GUC de A.
    ok = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {a['access_token']}"}
    )
    assert ok.status_code == 200
    # Request publica (sem token) continua 401 — e um login posterior nao
    # deve falhar por GUC residual. Validamos os dois lados.
    assert client.get("/auth/me").status_code == 401
    relogin = client.post(
        "/auth/login",
        json={"email": "a@acme.test", "password": "super-senha-123"},
    )
    assert relogin.status_code == 200, relogin.text


def test_suspended_tenant_returns_403(client) -> None:
    from api.db import get_admin_session
    from sqlalchemy import text

    a = _signup(client, slug="acme", email="a@acme.test")
    with get_admin_session() as session:
        session.execute(
            text("UPDATE tenants SET status = 'suspended' WHERE id = :tid"),
            {"tid": a["tenant_id"]},
        )
    resp = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {a['access_token']}"}
    )
    assert resp.status_code == 403
    assert "suspend" in resp.json()["detail"]


def test_canceled_tenant_returns_403(client) -> None:
    from api.db import get_admin_session
    from sqlalchemy import text

    a = _signup(client, slug="acme", email="a@acme.test")
    with get_admin_session() as session:
        session.execute(
            text("UPDATE tenants SET status = 'canceled' WHERE id = :tid"),
            {"tid": a["tenant_id"]},
        )
    resp = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {a['access_token']}"}
    )
    assert resp.status_code == 403
