"""Testes de integracao do CRUD de `/companies` (API-05).

Requerem um Postgres real com todas as migrations aplicadas (0001..0015).
Pulados quando `TEST_DATABASE_URL` nao estiver setada — mesmo padrao
dos testes de API-02/API-03.

Como rodar localmente:

    export TEST_DATABASE_URL="postgresql+psycopg://app_admin:***@localhost:5432/nfse_test"
    alembic -x url="$TEST_DATABASE_URL" upgrade head
    pytest apps/api/tests/test_companies_routes_integration.py -v

O banco apontado e TRUNCADO antes de cada teste. Nunca aponte para um
banco com dados de producao/staging.

Cobertura:
- CRUD feliz (criar, buscar, listar, atualizar, soft-delete).
- Validacao de CNPJ (DV invalido -> 422).
- Cross-tenant: tenant B nao ve/edita/remove company do tenant A (RLS).
- RBAC: viewer -> 403 em POST/PATCH/DELETE.
- Soft-delete e idempotente (segundo DELETE -> 404).
- Filtros por status e uf; paginacao.
- Limite do plano (`plans.limits.max_companies`) -> 409 ao estourar.
- PATCH com payload vazio -> 400.
"""

from __future__ import annotations

import os
from typing import Optional

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL nao definida — pulando integracao Postgres.",
)


VALID_CNPJ_A = "11222333000181"
VALID_CNPJ_B = "04252011000110"
VALID_CNPJ_C = "00000000000191"


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
                "TRUNCATE companies, refresh_tokens, tenant_users, users, "
                "subscriptions, tenants, plans CASCADE"
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
    """Cria tenant + user + tenant_users e devolve (tenant_id, user_id, access_token)."""
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


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _sample_company(**overrides) -> dict:
    base = {
        "cnpj": VALID_CNPJ_A,
        "razao_social": "Acme Servicos Contabeis LTDA",
        "nome_fantasia": "Acme",
        "municipio_ibge": "3550308",
        "uf": "SP",
        "status": "active",
        "portal_provider": "betha",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# CRUD feliz
# ---------------------------------------------------------------------------


def test_crud_feliz(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")

    # POST
    resp = client.post("/companies", json=_sample_company(), headers=_auth(token))
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["cnpj"] == VALID_CNPJ_A
    assert created["uf"] == "SP"
    cid = created["id"]

    # GET /{id}
    resp = client.get(f"/companies/{cid}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == cid

    # GET lista
    resp = client.get("/companies", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert len(body["items"]) == 1

    # PATCH
    resp = client.patch(
        f"/companies/{cid}",
        json={"razao_social": "Acme Brasil Holdings", "status": "paused"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    patched = resp.json()
    assert patched["razao_social"] == "Acme Brasil Holdings"
    assert patched["status"] == "paused"

    # DELETE (soft)
    resp = client.delete(f"/companies/{cid}", headers=_auth(token))
    assert resp.status_code == 204

    # Apos delete: 404 em GET e 2o DELETE
    assert client.get(f"/companies/{cid}", headers=_auth(token)).status_code == 404
    assert client.delete(f"/companies/{cid}", headers=_auth(token)).status_code == 404


def test_post_rejeita_cnpj_com_dv_invalido(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    resp = client.post(
        "/companies",
        json=_sample_company(cnpj="11222333000180"),
        headers=_auth(token),
    )
    assert resp.status_code == 422
    assert "CNPJ invalido" in resp.text


def test_post_recusa_cnpj_duplicado_no_mesmo_tenant(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    first = client.post("/companies", json=_sample_company(), headers=_auth(token))
    assert first.status_code == 201
    second = client.post("/companies", json=_sample_company(), headers=_auth(token))
    assert second.status_code == 409
    assert "CNPJ" in second.json()["detail"]


def test_delete_permite_reusar_cnpj(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    r1 = client.post("/companies", json=_sample_company(), headers=_auth(token))
    cid = r1.json()["id"]
    assert client.delete(f"/companies/{cid}", headers=_auth(token)).status_code == 204
    # O UNIQUE parcial permite re-criar o mesmo CNPJ apos soft-delete.
    r2 = client.post("/companies", json=_sample_company(), headers=_auth(token))
    assert r2.status_code == 201
    assert r2.json()["id"] != cid


# ---------------------------------------------------------------------------
# Cross-tenant (RLS)
# ---------------------------------------------------------------------------


def test_cross_tenant_isolado(client) -> None:
    _, _, token_a = _seed_tenant(slug="acme", email="a@acme.test")
    _, _, token_b = _seed_tenant(slug="beta", email="b@beta.test")

    resp = client.post("/companies", json=_sample_company(), headers=_auth(token_a))
    assert resp.status_code == 201
    cid_a = resp.json()["id"]

    # Tenant B nao enxerga.
    assert client.get(f"/companies/{cid_a}", headers=_auth(token_b)).status_code == 404
    lista_b = client.get("/companies", headers=_auth(token_b)).json()
    assert lista_b["total"] == 0

    # Tenant B nao edita nem remove.
    assert (
        client.patch(
            f"/companies/{cid_a}",
            json={"razao_social": "Hack"},
            headers=_auth(token_b),
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/companies/{cid_a}", headers=_auth(token_b)).status_code == 404
    )

    # Tenant A continua com a company intacta.
    a_body = client.get(f"/companies/{cid_a}", headers=_auth(token_a)).json()
    assert a_body["razao_social"] == "Acme Servicos Contabeis LTDA"


def test_mesmo_cnpj_em_tenants_distintos_e_permitido(client) -> None:
    _, _, token_a = _seed_tenant(slug="acme", email="a@acme.test")
    _, _, token_b = _seed_tenant(slug="beta", email="b@beta.test")
    assert (
        client.post("/companies", json=_sample_company(), headers=_auth(token_a)).status_code
        == 201
    )
    # UNIQUE e `(tenant_id, cnpj)` — tenant B pode usar o mesmo CNPJ.
    assert (
        client.post("/companies", json=_sample_company(), headers=_auth(token_b)).status_code
        == 201
    )


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


def test_viewer_nao_cria_nem_edita_nem_remove(client) -> None:
    # Owner seeda a company, viewer no mesmo tenant so deve ler.
    tid, _, owner_token = _seed_tenant(slug="acme", email="owner@acme.test")
    # Viewer precisa de outro user no mesmo tenant.
    from api.db import get_admin_session
    from api.security.jwt import create_access_token
    from sqlalchemy import text

    with get_admin_session() as session:
        urow = session.execute(
            text(
                """
                INSERT INTO users (email, password_hash, name, status)
                VALUES ('v@acme.test', 'x', 'Viewer', 'active')
                RETURNING id
                """
            )
        ).one()
        uid = str(urow.id)
        session.execute(
            text(
                """
                INSERT INTO tenant_users (tenant_id, user_id, role, accepted_at)
                VALUES (:tid, :uid, 'viewer', now())
                """
            ),
            {"tid": tid, "uid": uid},
        )

    viewer_token = create_access_token(user_id=uid, tenant_id=tid, role="viewer")

    created = client.post(
        "/companies", json=_sample_company(), headers=_auth(owner_token)
    )
    cid = created.json()["id"]

    # Viewer le ok.
    assert client.get("/companies", headers=_auth(viewer_token)).status_code == 200
    assert (
        client.get(f"/companies/{cid}", headers=_auth(viewer_token)).status_code == 200
    )

    # Viewer nao escreve.
    resp = client.post(
        "/companies",
        json=_sample_company(cnpj=VALID_CNPJ_B),
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 403
    assert "permissao insuficiente" in resp.json()["detail"]

    resp = client.patch(
        f"/companies/{cid}",
        json={"razao_social": "Novo"},
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 403

    resp = client.delete(f"/companies/{cid}", headers=_auth(viewer_token))
    assert resp.status_code == 403


def test_operator_nao_remove(client) -> None:
    tid, _, owner_token = _seed_tenant(slug="acme", email="owner@acme.test")
    from api.db import get_admin_session
    from api.security.jwt import create_access_token
    from sqlalchemy import text

    with get_admin_session() as session:
        urow = session.execute(
            text(
                """
                INSERT INTO users (email, password_hash, name, status)
                VALUES ('op@acme.test', 'x', 'Op', 'active')
                RETURNING id
                """
            )
        ).one()
        uid = str(urow.id)
        session.execute(
            text(
                """
                INSERT INTO tenant_users (tenant_id, user_id, role, accepted_at)
                VALUES (:tid, :uid, 'operator', now())
                """
            ),
            {"tid": tid, "uid": uid},
        )

    op_token = create_access_token(user_id=uid, tenant_id=tid, role="operator")

    created = client.post(
        "/companies", json=_sample_company(), headers=_auth(owner_token)
    )
    cid = created.json()["id"]

    # Operator pode criar e editar, mas nao remover.
    assert (
        client.post(
            "/companies",
            json=_sample_company(cnpj=VALID_CNPJ_B),
            headers=_auth(op_token),
        ).status_code
        == 201
    )
    assert (
        client.patch(
            f"/companies/{cid}",
            json={"notes": "atualizado por operator"},
            headers=_auth(op_token),
        ).status_code
        == 200
    )
    assert client.delete(f"/companies/{cid}", headers=_auth(op_token)).status_code == 403


# ---------------------------------------------------------------------------
# Filtros e paginacao
# ---------------------------------------------------------------------------


def test_filtros_status_e_uf_e_paginacao(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    # 3 companies: 2 active SP + 1 paused RJ.
    client.post("/companies", json=_sample_company(cnpj=VALID_CNPJ_A), headers=_auth(token))
    client.post(
        "/companies",
        json=_sample_company(cnpj=VALID_CNPJ_B, uf="SP"),
        headers=_auth(token),
    )
    client.post(
        "/companies",
        json=_sample_company(cnpj=VALID_CNPJ_C, uf="RJ", status="paused"),
        headers=_auth(token),
    )

    # uf=SP
    body = client.get("/companies?uf=SP", headers=_auth(token)).json()
    assert body["total"] == 2

    # status=paused
    body = client.get("/companies?status=paused", headers=_auth(token)).json()
    assert body["total"] == 1
    assert body["items"][0]["uf"] == "RJ"

    # status=active & uf=SP
    body = client.get(
        "/companies?status=active&uf=SP", headers=_auth(token)
    ).json()
    assert body["total"] == 2

    # paginacao: page_size=1
    body = client.get("/companies?page=1&page_size=1", headers=_auth(token)).json()
    assert body["total"] == 3
    assert len(body["items"]) == 1
    body2 = client.get("/companies?page=2&page_size=1", headers=_auth(token)).json()
    assert len(body2["items"]) == 1
    assert body2["items"][0]["id"] != body["items"][0]["id"]


def test_lista_oculta_soft_deleted(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    r = client.post("/companies", json=_sample_company(), headers=_auth(token))
    cid = r.json()["id"]
    client.delete(f"/companies/{cid}", headers=_auth(token))
    body = client.get("/companies", headers=_auth(token)).json()
    assert body["total"] == 0


# ---------------------------------------------------------------------------
# Limite de plano (ADR-004)
# ---------------------------------------------------------------------------


def test_limite_de_plano_bloqueia_criacao(client) -> None:
    from api.db import get_admin_session
    from sqlalchemy import text

    # Seeda um plano com cap = 1.
    with get_admin_session() as session:
        session.execute(
            text(
                """
                INSERT INTO plans (code, name, limits, price_cents, active)
                VALUES ('starter', 'Starter',
                        '{"max_companies": 1}'::jsonb, 0, true)
                """
            )
        )

    _, _, token = _seed_tenant(
        slug="limitado", email="owner@limitado.test", plan_code="starter"
    )

    r1 = client.post("/companies", json=_sample_company(), headers=_auth(token))
    assert r1.status_code == 201

    r2 = client.post(
        "/companies",
        json=_sample_company(cnpj=VALID_CNPJ_B),
        headers=_auth(token),
    )
    assert r2.status_code == 409
    assert "limite" in r2.json()["detail"]


def test_sem_plano_nao_aplica_limite(client) -> None:
    _, _, token = _seed_tenant(slug="nopl", email="owner@nopl.test", plan_code=None)
    assert (
        client.post(
            "/companies", json=_sample_company(), headers=_auth(token)
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/companies",
            json=_sample_company(cnpj=VALID_CNPJ_B),
            headers=_auth(token),
        ).status_code
        == 201
    )


def test_plano_sem_chave_max_companies_nao_aplica_limite(client) -> None:
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        session.execute(
            text(
                """
                INSERT INTO plans (code, name, limits, price_cents, active)
                VALUES ('enterprise', 'Enterprise', '{}'::jsonb, 9900, true)
                """
            )
        )
    _, _, token = _seed_tenant(
        slug="ent", email="ent@acme.test", plan_code="enterprise"
    )
    for cnpj in (VALID_CNPJ_A, VALID_CNPJ_B, VALID_CNPJ_C):
        r = client.post(
            "/companies", json=_sample_company(cnpj=cnpj), headers=_auth(token)
        )
        assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# Detalhes de edge-cases
# ---------------------------------------------------------------------------


def test_patch_vazio_retorna_400(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    r = client.post("/companies", json=_sample_company(), headers=_auth(token))
    cid = r.json()["id"]
    resp = client.patch(f"/companies/{cid}", json={}, headers=_auth(token))
    assert resp.status_code == 400


def test_token_ausente_retorna_401(client) -> None:
    resp = client.get("/companies")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_openapi_lista_endpoints_companies(client) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/companies" in paths
    assert "/companies/{company_id}" in paths
    # Metodos.
    assert set(paths["/companies"].keys()) >= {"get", "post"}
    assert set(paths["/companies/{company_id}"].keys()) >= {"get", "patch", "delete"}
