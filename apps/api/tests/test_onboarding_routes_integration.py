"""Testes de integracao de `/onboarding/*` (APP-11).

Exige Postgres real com as migrations aplicadas. Pulados quando
`TEST_DATABASE_URL` nao estiver setada — mesmo padrao dos outros testes
de integracao.

Cobertura:
- Caminho feliz: primeira chamada insere em `notifications` com
  (channel='email', type='first_collection_done').
- Idempotencia: segunda chamada retorna `already_recorded=True` com o
  mesmo `notification_id`.
- Viewer pode registrar (qualquer membro autenticado tem acesso).
- RLS isola cross-tenant: tenant B nao enxerga a notif do tenant A.
- Sem token -> 401.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL nao definida — pulando integracao Postgres.",
)


@pytest.fixture()
def env_setup():
    os.environ["API_DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ.setdefault("API_JWT_SECRET", "integration-test-secret")
    os.environ.setdefault("API_ENVIRONMENT", "development")
    os.environ.setdefault("API_LOGIN_RATE_LIMIT", "1000/minute")

    from api.config import get_settings
    from api.db import reset_engine_for_tests

    get_settings.cache_clear()  # type: ignore[attr-defined]
    reset_engine_for_tests()
    yield
    reset_engine_for_tests()


@pytest.fixture()
def client(env_setup):
    from api.db import get_admin_session
    from api.main import create_app
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    with get_admin_session() as session:
        session.execute(
            text(
                "TRUNCATE notifications, audit_logs, tenant_users, "
                "users, tenants CASCADE"
            )
        )

    app = create_app()
    with TestClient(app) as c:
        yield c


def _seed_tenant(
    *,
    slug: str,
    email: str,
    role: str = "owner",
) -> tuple[str, str, str]:
    from api.db import get_admin_session
    from api.security.jwt import create_access_token
    from sqlalchemy import text

    with get_admin_session() as session:
        trow = session.execute(
            text(
                """
                INSERT INTO tenants (name, slug)
                VALUES (:name, :slug)
                RETURNING id
                """
            ),
            {"name": slug.title(), "slug": slug},
        ).one()
        tenant_id = str(trow.id)

        urow = session.execute(
            text(
                """
                INSERT INTO users (email, password_hash, name, status)
                VALUES (:email, 'x', :name, 'active')
                RETURNING id
                """
            ),
            {"email": email, "name": email.split("@")[0]},
        ).one()
        user_id = str(urow.id)

        session.execute(
            text(
                """
                INSERT INTO tenant_users (tenant_id, user_id, role, accepted_at)
                VALUES (:tid, :uid, :role, now())
                """
            ),
            {"tid": tenant_id, "uid": user_id, "role": role},
        )

    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role=role)
    return tenant_id, user_id, token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_feliz_insere_notification_first_collection_done(client) -> None:
    from api.db import get_admin_session
    from sqlalchemy import text

    tid, uid, token = _seed_tenant(slug="acme", email="owner@acme.test")

    resp = client.post("/onboarding/first-collection-done", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["already_recorded"] is False
    assert body["notification_id"]

    with get_admin_session() as session:
        row = session.execute(
            text(
                """
                SELECT channel, type, status, tenant_id, user_id
                  FROM notifications
                 WHERE id = :nid
                """
            ),
            {"nid": body["notification_id"]},
        ).one()
    assert row.channel == "email"
    assert row.type == "first_collection_done"
    assert row.status == "pending"
    assert str(row.tenant_id) == tid
    assert str(row.user_id) == uid


def test_idempotente_segunda_chamada_marca_already_recorded(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")

    first = client.post("/onboarding/first-collection-done", headers=_auth(token))
    assert first.status_code == 200
    first_id = first.json()["notification_id"]

    second = client.post("/onboarding/first-collection-done", headers=_auth(token))
    assert second.status_code == 200
    body = second.json()
    assert body["already_recorded"] is True
    assert body["notification_id"] == first_id


def test_viewer_pode_registrar(client) -> None:
    _, _, token = _seed_tenant(
        slug="viewerco", email="viewer@viewerco.test", role="viewer",
    )
    resp = client.post("/onboarding/first-collection-done", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["already_recorded"] is False


def test_sem_token_retorna_401(client) -> None:
    resp = client.post("/onboarding/first-collection-done")
    assert resp.status_code == 401


def test_rls_isola_entre_tenants(client) -> None:
    from api.db import get_admin_session
    from sqlalchemy import text

    tid_a, uid_a, token_a = _seed_tenant(slug="tenantA", email="a@a.test")
    _, uid_b, token_b = _seed_tenant(slug="tenantB", email="b@b.test")

    # Usuario A registra.
    ra = client.post("/onboarding/first-collection-done", headers=_auth(token_a))
    nid_a = ra.json()["notification_id"]

    # Usuario B registra — deve criar uma notif diferente (nao enxerga A).
    rb = client.post("/onboarding/first-collection-done", headers=_auth(token_b))
    nid_b = rb.json()["notification_id"]
    assert rb.json()["already_recorded"] is False
    assert nid_a != nid_b

    # Conferindo direto no banco que as notifs estao em tenants diferentes.
    with get_admin_session() as session:
        rows = session.execute(
            text(
                "SELECT id, tenant_id, user_id FROM notifications "
                "WHERE id IN (:a, :b)"
            ),
            {"a": nid_a, "b": nid_b},
        ).all()
    assert len(rows) == 2
    tenant_ids = {str(r.tenant_id) for r in rows}
    user_ids = {str(r.user_id) for r in rows}
    # Duas notifs em tenants distintos — a policy RLS separou corretamente.
    assert len(tenant_ids) == 2
    assert tid_a in tenant_ids
    assert uid_a in user_ids and uid_b in user_ids
