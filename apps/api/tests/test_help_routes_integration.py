"""Integracao de `/help`: agregacao, RBAC e isolamento por tenant."""

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
                "TRUNCATE help_metrics_daily, tenant_users, users, tenants CASCADE"
            )
        )

    with TestClient(create_app()) as test_client:
        yield test_client


def _seed(*, slug: str, role: str) -> tuple[str, str]:
    from api.db import get_admin_session
    from api.security.jwt import create_access_token
    from sqlalchemy import text

    with get_admin_session() as session:
        tenant = session.execute(
            text("INSERT INTO tenants (name, slug) VALUES (:n, :s) RETURNING id"),
            {"n": slug.title(), "s": slug},
        ).one()
        user = session.execute(
            text(
                "INSERT INTO users (email, password_hash, name, status) "
                "VALUES (:e, 'x', :n, 'active') RETURNING id"
            ),
            {"e": f"{role}@{slug}.test", "n": role},
        ).one()
        session.execute(
            text(
                "INSERT INTO tenant_users (tenant_id, user_id, role, accepted_at) "
                "VALUES (:tid, :uid, :role, now())"
            ),
            {"tid": str(tenant.id), "uid": str(user.id), "role": role},
        )

    token = create_access_token(
        user_id=user.id, tenant_id=tenant.id, role=role
    )
    return str(tenant.id), token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_event_upserts_daily_counter_and_insights(client) -> None:
    tenant_id, token = _seed(slug="help-admin", role="admin")
    payload = {
        "event_type": "article_opened",
        "article_slug": "schedules",
        "route_key": "schedules",
    }

    assert client.post("/help/events", json=payload, headers=_auth(token)).status_code == 204
    assert client.post("/help/events", json=payload, headers=_auth(token)).status_code == 204

    response = client.get("/help/insights?days=7", headers=_auth(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["totals"]["article_opened"] == 2
    assert body["rows"] == [
        {
            "article_slug": "schedules",
            "route_key": "schedules",
            "article_opened": 2,
            "search_performed": 0,
            "search_no_results": 0,
            "tour_started": 0,
            "tour_completed": 0,
            "tour_skipped": 0,
            "tour_failed": 0,
            "feedback_yes": 0,
            "feedback_no": 0,
        }
    ]

    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        row = session.execute(
            text(
                "SELECT tenant_id, role, count FROM help_metrics_daily"
            )
        ).one()
    assert str(row.tenant_id) == tenant_id
    assert row.role == "admin"
    assert row.count == 2


def test_viewer_records_but_cannot_read_insights(client) -> None:
    _, token = _seed(slug="help-viewer", role="viewer")
    response = client.post(
        "/help/events",
        json={"event_type": "search_performed", "route_key": "help"},
        headers=_auth(token),
    )
    assert response.status_code == 204
    assert client.get("/help/insights", headers=_auth(token)).status_code == 403


def test_invalid_days_and_payload_do_not_persist(client) -> None:
    _, token = _seed(slug="help-owner", role="owner")
    assert client.get("/help/insights?days=10", headers=_auth(token)).status_code == 422
    response = client.post(
        "/help/events",
        json={
            "event_type": "search_performed",
            "route_key": "help",
            "query": "nao armazenar",
        },
        headers=_auth(token),
    )
    assert response.status_code == 422


def test_insights_are_isolated_between_tenants(client) -> None:
    _, token_a = _seed(slug="help-a", role="admin")
    _, token_b = _seed(slug="help-b", role="admin")
    payload = {
        "event_type": "feedback_yes",
        "article_slug": "dashboard",
        "route_key": "dashboard",
    }
    client.post("/help/events", json=payload, headers=_auth(token_a))

    body_a = client.get("/help/insights", headers=_auth(token_a)).json()
    body_b = client.get("/help/insights", headers=_auth(token_b)).json()
    assert body_a["totals"]["feedback_yes"] == 1
    assert body_b["totals"]["feedback_yes"] == 0
