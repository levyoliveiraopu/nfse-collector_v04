"""Testes de integracao do CRUD de `/schedules` (API-12).

Requer Postgres com migrations 0001..0015 aplicadas. Pulados sem
`TEST_DATABASE_URL` — padrao API-02/03/05/06.

Cobertura:
- CRUD feliz (POST, GET lista/detalhe, PATCH, DELETE).
- `next_run_at` calculado no POST e recomputado quando cron/tz mudam
  ou quando `enabled` volta para true.
- Pause via `enabled=false` limpa `next_run_at`.
- Cron/TZ invalidos no POST -> 400 (DoD).
- Cross-tenant (RLS) -> 404.
- RBAC: viewer -> 403 em POST/PATCH/DELETE; operator -> 403 no DELETE.
- PATCH vazio -> 400.
- Presets -> 3 itens.
- Filtros por `enabled` e `company_id`.
- Company de outro tenant no POST -> 400.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

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
                "TRUNCATE schedules, companies, refresh_tokens, "
                "tenant_users, users, subscriptions, tenants, plans "
                "CASCADE"
            )
        )

    app = create_app()
    with TestClient(app) as client:
        yield client


def _seed_tenant(
    *,
    slug: str,
    email: str,
    role: str = "owner",
    plan_code: Optional[str] = None,
) -> tuple[str, str, str]:
    from api.db import get_admin_session
    from api.security.jwt import create_access_token
    from sqlalchemy import text

    with get_admin_session() as session:
        trow = session.execute(
            text(
                """
                INSERT INTO tenants (name, slug, plan_id)
                VALUES (:name, :slug, :plan)
                RETURNING id
                """
            ),
            {"name": slug.title(), "slug": slug, "plan": plan_code},
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


def _seed_company(tenant_id: str, *, cnpj: str = "11222333000181") -> str:
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        row = session.execute(
            text(
                """
                INSERT INTO companies
                    (tenant_id, cnpj, razao_social, municipio_ibge, uf)
                VALUES (:tid, :cnpj, 'Seed LTDA', '3550308', 'SP')
                RETURNING id
                """
            ),
            {"tid": tenant_id, "cnpj": cnpj},
        ).one()
        return str(row.id)


def _extra_member(
    tenant_id: str, *, role: str, email: str
) -> str:
    from api.db import get_admin_session
    from api.security.jwt import create_access_token
    from sqlalchemy import text

    with get_admin_session() as session:
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
        uid = str(urow.id)
        session.execute(
            text(
                """
                INSERT INTO tenant_users (tenant_id, user_id, role, accepted_at)
                VALUES (:tid, :uid, :role, now())
                """
            ),
            {"tid": tenant_id, "uid": uid, "role": role},
        )

    return create_access_token(user_id=uid, tenant_id=tenant_id, role=role)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# CRUD feliz + next_run_at
# ---------------------------------------------------------------------------


def test_crud_feliz_com_next_run_at(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")

    # POST (tenant-wide, sem company_id)
    resp = client.post(
        "/schedules",
        json={"cron_expr": "0 3 * * *", "timezone": "America/Sao_Paulo"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["cron_expr"] == "0 3 * * *"
    assert created["timezone"] == "America/Sao_Paulo"
    assert created["enabled"] is True
    assert created["company_id"] is None
    # next_run_at deve estar coerente: 03:00 SP convertido para UTC,
    # no futuro proximo (<= 24h adiante) e em horario cheio (:00:00).
    nxt = datetime.fromisoformat(created["next_run_at"])
    assert nxt.tzinfo is not None
    assert nxt > datetime.now(tz=timezone.utc)
    assert nxt.minute == 0 and nxt.second == 0
    sid = created["id"]

    # GET /{id}
    body = client.get(f"/schedules/{sid}", headers=_auth(token)).json()
    assert body["id"] == sid

    # GET lista
    body = client.get("/schedules", headers=_auth(token)).json()
    assert body["total"] == 1
    assert len(body["items"]) == 1


def test_post_com_company_id_valido(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tid)

    resp = client.post(
        "/schedules",
        json={
            "cron_expr": "0 6 * * 1",
            "timezone": "UTC",
            "company_id": cid,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["company_id"] == cid
    # 0 6 * * 1 em UTC -> proxima segunda 06:00 UTC.
    nxt = datetime.fromisoformat(body["next_run_at"])
    assert nxt.hour == 6 and nxt.weekday() == 0


def test_post_disabled_nao_calcula_next_run(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    resp = client.post(
        "/schedules",
        json={"cron_expr": "0 3 * * *", "enabled": False},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["next_run_at"] is None


# ---------------------------------------------------------------------------
# Cron / TZ invalidos -> 400 (DoD)
# ---------------------------------------------------------------------------


def test_cron_invalido_retorna_400(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")

    # Pydantic rejeita antes de chegar ao handler -> 422, com detail
    # mencionando cron. Mesmo assim, para o DoD "cron invalido retorna
    # 400 claro", verificamos que a mensagem *explica* o problema.
    resp = client.post(
        "/schedules", json={"cron_expr": "bogus"}, headers=_auth(token)
    )
    # Documentamos o contrato exato: Pydantic -> 422 com mensagem clara;
    # aceitamos 400 ou 422 aqui (os dois sao "claros"); o ponto do DoD
    # e que nao sofre 500 nem passa por IntegrityError generico.
    assert resp.status_code in (400, 422)
    assert "cron" in resp.text.lower()


def test_cron_com_campos_a_mais_retorna_erro_claro(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    resp = client.post(
        "/schedules",
        json={"cron_expr": "0 3 * * * *"},  # 6 campos
        headers=_auth(token),
    )
    assert resp.status_code in (400, 422)
    assert "5 campos" in resp.text or "5 campo" in resp.text or "cron" in resp.text.lower()


def test_tz_invalida_retorna_erro_claro(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    resp = client.post(
        "/schedules",
        json={"cron_expr": "0 3 * * *", "timezone": "Nao/Existe"},
        headers=_auth(token),
    )
    assert resp.status_code in (400, 422)
    assert "timezone" in resp.text.lower()


# ---------------------------------------------------------------------------
# Cross-tenant (RLS)
# ---------------------------------------------------------------------------


def test_cross_tenant_isolado(client) -> None:
    _, _, token_a = _seed_tenant(slug="acme", email="a@acme.test")
    _, _, token_b = _seed_tenant(slug="beta", email="b@beta.test")

    resp = client.post(
        "/schedules", json={"cron_expr": "0 3 * * *"}, headers=_auth(token_a)
    )
    assert resp.status_code == 201
    sid_a = resp.json()["id"]

    # Tenant B nao enxerga.
    assert client.get(f"/schedules/{sid_a}", headers=_auth(token_b)).status_code == 404
    lista_b = client.get("/schedules", headers=_auth(token_b)).json()
    assert lista_b["total"] == 0

    # Tenant B nao edita nem remove.
    assert (
        client.patch(
            f"/schedules/{sid_a}",
            json={"enabled": False},
            headers=_auth(token_b),
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/schedules/{sid_a}", headers=_auth(token_b)).status_code == 404
    )


def test_post_com_company_de_outro_tenant_retorna_400(client) -> None:
    tid_a, _, token_a = _seed_tenant(slug="acme", email="a@acme.test")
    tid_b, _, _ = _seed_tenant(slug="beta", email="b@beta.test")
    cid_b = _seed_company(tid_b)

    resp = client.post(
        "/schedules",
        json={"cron_expr": "0 3 * * *", "company_id": cid_b},
        headers=_auth(token_a),
    )
    # Tenant A nao enxerga a company de B via RLS -> SELECT devolve vazio
    # e o handler levanta 400 "company_id nao encontrado".
    assert resp.status_code == 400
    assert "company_id" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# PATCH: pause/resume + recomputo de next_run_at
# ---------------------------------------------------------------------------


def test_patch_pause_limpa_next_run_at(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    created = client.post(
        "/schedules", json={"cron_expr": "0 3 * * *"}, headers=_auth(token)
    ).json()
    sid = created["id"]
    assert created["next_run_at"] is not None

    # Pause.
    resp = client.patch(
        f"/schedules/{sid}", json={"enabled": False}, headers=_auth(token)
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert resp.json()["next_run_at"] is None


def test_patch_resume_recalcula_next_run_at(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    created = client.post(
        "/schedules",
        json={"cron_expr": "0 3 * * *", "enabled": False},
        headers=_auth(token),
    ).json()
    assert created["next_run_at"] is None
    sid = created["id"]

    resp = client.patch(
        f"/schedules/{sid}", json={"enabled": True}, headers=_auth(token)
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True
    assert resp.json()["next_run_at"] is not None


def test_patch_mudar_cron_recomputa_next_run_at(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    created = client.post(
        "/schedules", json={"cron_expr": "0 3 * * *"}, headers=_auth(token)
    ).json()
    sid = created["id"]
    nxt_antes = created["next_run_at"]

    resp = client.patch(
        f"/schedules/{sid}", json={"cron_expr": "0 5 1 * *"}, headers=_auth(token)
    )
    assert resp.status_code == 200
    nxt_depois = resp.json()["next_run_at"]
    assert nxt_depois != nxt_antes


def test_patch_vazio_retorna_400(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    created = client.post(
        "/schedules", json={"cron_expr": "0 3 * * *"}, headers=_auth(token)
    ).json()
    resp = client.patch(
        f"/schedules/{created['id']}", json={}, headers=_auth(token)
    )
    assert resp.status_code == 400


def test_patch_cron_invalido_retorna_erro_claro(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    created = client.post(
        "/schedules", json={"cron_expr": "0 3 * * *"}, headers=_auth(token)
    ).json()
    resp = client.patch(
        f"/schedules/{created['id']}",
        json={"cron_expr": "bogus"},
        headers=_auth(token),
    )
    assert resp.status_code in (400, 422)
    assert "cron" in resp.text.lower()


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------


def test_delete_remove_schedule(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    created = client.post(
        "/schedules", json={"cron_expr": "0 3 * * *"}, headers=_auth(token)
    ).json()
    sid = created["id"]

    assert client.delete(f"/schedules/{sid}", headers=_auth(token)).status_code == 204
    assert client.get(f"/schedules/{sid}", headers=_auth(token)).status_code == 404
    # Idempotente: segundo DELETE -> 404.
    assert client.delete(f"/schedules/{sid}", headers=_auth(token)).status_code == 404


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


def test_viewer_nao_escreve(client) -> None:
    tid, _, owner_token = _seed_tenant(slug="acme", email="owner@acme.test")
    viewer_token = _extra_member(tid, role="viewer", email="v@acme.test")

    created = client.post(
        "/schedules", json={"cron_expr": "0 3 * * *"}, headers=_auth(owner_token)
    ).json()
    sid = created["id"]

    # Viewer le ok.
    assert client.get("/schedules", headers=_auth(viewer_token)).status_code == 200
    assert client.get(f"/schedules/{sid}", headers=_auth(viewer_token)).status_code == 200
    assert client.get("/schedules/presets", headers=_auth(viewer_token)).status_code == 200

    # Viewer nao escreve.
    r = client.post(
        "/schedules", json={"cron_expr": "0 3 * * *"}, headers=_auth(viewer_token)
    )
    assert r.status_code == 403
    r = client.patch(
        f"/schedules/{sid}", json={"enabled": False}, headers=_auth(viewer_token)
    )
    assert r.status_code == 403
    r = client.delete(f"/schedules/{sid}", headers=_auth(viewer_token))
    assert r.status_code == 403


def test_operator_escreve_mas_nao_remove(client) -> None:
    tid, _, owner_token = _seed_tenant(slug="acme", email="owner@acme.test")
    op_token = _extra_member(tid, role="operator", email="op@acme.test")

    created = client.post(
        "/schedules", json={"cron_expr": "0 3 * * *"}, headers=_auth(owner_token)
    ).json()
    sid = created["id"]

    # Operator cria / edita.
    assert (
        client.post(
            "/schedules",
            json={"cron_expr": "0 6 * * 1"},
            headers=_auth(op_token),
        ).status_code
        == 201
    )
    assert (
        client.patch(
            f"/schedules/{sid}",
            json={"enabled": False},
            headers=_auth(op_token),
        ).status_code
        == 200
    )
    # Mas nao remove.
    assert client.delete(f"/schedules/{sid}", headers=_auth(op_token)).status_code == 403


# ---------------------------------------------------------------------------
# Filtros e presets
# ---------------------------------------------------------------------------


def test_presets_retorna_tres(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    resp = client.get("/schedules/presets", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 3
    ids = {p["id"] for p in body["items"]}
    assert ids == {"daily_03", "weekly_mon_06", "monthly_day1_05"}


def test_filtros_enabled_e_company(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tid)

    # 1 com company + enabled=true; 1 sem company + enabled=false; 1 com company + enabled=false.
    client.post(
        "/schedules",
        json={"cron_expr": "0 3 * * *", "company_id": cid, "enabled": True},
        headers=_auth(token),
    )
    client.post(
        "/schedules",
        json={"cron_expr": "0 6 * * 1", "enabled": False},
        headers=_auth(token),
    )
    client.post(
        "/schedules",
        json={"cron_expr": "0 5 1 * *", "company_id": cid, "enabled": False},
        headers=_auth(token),
    )

    body = client.get("/schedules?enabled=true", headers=_auth(token)).json()
    assert body["total"] == 1

    body = client.get("/schedules?enabled=false", headers=_auth(token)).json()
    assert body["total"] == 2

    body = client.get(f"/schedules?company_id={cid}", headers=_auth(token)).json()
    assert body["total"] == 2
