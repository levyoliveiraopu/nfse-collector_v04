"""Testes de integracao de `/executions` (API-07).

Exige Postgres real com as migrations aplicadas. Pulados quando
`TEST_DATABASE_URL` nao estiver setada — mesmo padrao de API-02/03/05.

A fila Redis e substituida por `fakeredis` no conftest local, entao
este teste nao precisa de um Redis rodando — apenas do Postgres.

Como rodar:

    export TEST_DATABASE_URL="postgresql+psycopg://app_admin:***@localhost:5432/nfse_test"
    alembic -x url="$TEST_DATABASE_URL" upgrade head
    pytest apps/api/tests/test_executions_routes_integration.py -v

Cobertura:
- Caminho feliz: N companies com credencial valida -> N executions
  em status `queued` + N jobs no fake Redis.
- `GET /executions/{id}` devolve o que o POST criou.
- Cross-tenant: tenant B recebe 404 ao buscar execution do tenant A.
- Viewer -> 403 no POST, 200 no GET.
- Operator pode disparar.
- Company inexistente/cross-tenant -> 422 (`companies_not_found`).
- Company sem credencial ativa -> 422 (`credential_missing_or_expired`).
- Company com credencial vencida -> 422.
- `period_end < period_start` -> 422 (Pydantic).
- Redis offline antes do INSERT -> 502, DB intocado.
- Redis quebra no meio do enqueue -> execution marcada como `failed`
  com `error_summary='enqueue_failed'`.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Optional

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL nao definida — pulando integracao Postgres.",
)

fakeredis = pytest.importorskip("fakeredis")
rq = pytest.importorskip("rq")


VALID_CNPJ_A = "11222333000181"
VALID_CNPJ_B = "04252011000110"


@pytest.fixture()
def env_setup():
    os.environ["API_DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ.setdefault("API_JWT_SECRET", "integration-test-secret")
    os.environ.setdefault("API_ENVIRONMENT", "development")
    os.environ.setdefault("API_LOGIN_RATE_LIMIT", "1000/minute")
    # Placeholder — fakeredis substitui na fixture `client`.
    os.environ.setdefault("API_REDIS_URL", "redis://fake/0")

    from api.config import get_settings
    from api.db import reset_engine_for_tests
    from api.queue import reset_queue_client_for_tests

    get_settings.cache_clear()  # type: ignore[attr-defined]
    reset_engine_for_tests()
    reset_queue_client_for_tests()
    yield
    reset_engine_for_tests()
    reset_queue_client_for_tests()


@pytest.fixture()
def fake_redis():
    """Fake Redis compartilhado entre todas as chamadas do teste."""
    return fakeredis.FakeStrictRedis()


@pytest.fixture()
def client(env_setup, fake_redis):
    from api import queue as queue_mod
    from api.db import get_admin_session
    from api.main import create_app
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    # TRUNCATE todas as tabelas tocadas nos testes.
    with get_admin_session() as session:
        session.execute(
            text(
                "TRUNCATE audit_logs, execution_items, executions, "
                "company_credentials, companies, refresh_tokens, "
                "tenant_users, users, subscriptions, tenants, plans CASCADE"
            )
        )

    # Injeta fake redis + RQ Queue real rodando sobre ele.
    q = rq.Queue(name="nfse-executions-test", connection=fake_redis)
    queue_mod.set_queue_client_for_tests(fake_redis, q)

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


def _add_user(
    tenant_id: str, *, email: str, role: str
) -> tuple[str, str]:
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

    return uid, create_access_token(user_id=uid, tenant_id=tenant_id, role=role)


def _seed_company(
    *, tenant_id: str, cnpj: str = VALID_CNPJ_A, with_credential: bool = True,
    credential_expired: bool = False,
) -> str:
    """Cria company + (opcional) credencial ativa via admin session."""
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        crow = session.execute(
            text(
                """
                INSERT INTO companies (
                    tenant_id, cnpj, razao_social, municipio_ibge, uf, status
                ) VALUES (:tid, :cnpj, 'Acme', '3550308', 'SP', 'active')
                RETURNING id
                """
            ),
            {"tid": tenant_id, "cnpj": cnpj},
        ).one()
        cid = str(crow.id)

        if with_credential:
            not_after = (
                "now() - interval '1 day'"
                if credential_expired
                else "now() + interval '365 days'"
            )
            session.execute(
                text(
                    f"""
                    INSERT INTO company_credentials (
                        tenant_id, company_id, type, pfx_object_key,
                        pfx_password_ciphertext, cert_fingerprint,
                        cert_not_before, cert_not_after, status
                    ) VALUES (
                        :tid, :cid, 'pfx_a1', 'stub-key',
                        decode('01', 'hex'), 'stub-fp',
                        now() - interval '30 days',
                        {not_after},
                        'active'
                    )
                    """
                ),
                {"tid": tenant_id, "cid": cid},
            )

    return cid


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Caminho feliz
# ---------------------------------------------------------------------------


def test_post_cria_N_executions_e_N_jobs(client, fake_redis) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid_a = _seed_company(tenant_id=tid, cnpj=VALID_CNPJ_A)
    cid_b = _seed_company(tenant_id=tid, cnpj=VALID_CNPJ_B)

    payload = {
        "company_ids": [cid_a, cid_b],
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
    }
    resp = client.post("/executions", json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body["created"]) == 2
    for item in body["created"]:
        assert item["status"] == "queued"
        assert item["job_id"]
        assert item["enqueue_error"] is None

    # N jobs na fila fake.
    q = rq.Queue(name="nfse-executions-test", connection=fake_redis)
    assert q.count == 2
    args = sorted(str(j.args[0]) for j in q.jobs)
    created_ids = sorted(item["execution_id"] for item in body["created"])
    assert args == created_ids

    # GET de um dos ids devolve status queued + contadores zerados.
    eid = body["created"][0]["execution_id"]
    resp = client.get(f"/executions/{eid}", headers=_auth(token))
    assert resp.status_code == 200
    got = resp.json()
    assert got["status"] == "queued"
    assert got["items_total"] == 0
    assert got["period_start"] == "2026-01-01"
    assert got["period_end"] == "2026-01-31"
    assert got["trigger"] == "manual"


def test_post_com_dry_run_true_propaga_no_meta(client, fake_redis) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    resp = client.post(
        "/executions",
        json={
            "company_ids": [cid],
            "period_start": "2026-02-01",
            "period_end": "2026-02-28",
            "dry_run": True,
            "trigger": "api",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text

    q = rq.Queue(name="nfse-executions-test", connection=fake_redis)
    assert q.count == 1
    job = q.jobs[0]
    assert job.meta == {"tenant_id": tid, "dry_run": True}


def test_get_cross_tenant_404(client) -> None:
    tid_a, _, token_a = _seed_tenant(slug="a", email="a@a.test")
    _, _, token_b = _seed_tenant(slug="b", email="b@b.test")
    cid = _seed_company(tenant_id=tid_a)

    resp = client.post(
        "/executions",
        json={
            "company_ids": [cid],
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_auth(token_a),
    )
    eid = resp.json()["created"][0]["execution_id"]
    assert client.get(f"/executions/{eid}", headers=_auth(token_b)).status_code == 404


def test_post_company_de_outro_tenant_422(client) -> None:
    tid_a, _, _ = _seed_tenant(slug="a", email="a@a.test")
    _, _, token_b = _seed_tenant(slug="b", email="b@b.test")
    cid_a = _seed_company(tenant_id=tid_a)

    resp = client.post(
        "/executions",
        json={
            "company_ids": [cid_a],
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_auth(token_b),
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "companies_not_found"


def test_post_company_sem_credencial_422(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid, with_credential=False)
    resp = client.post(
        "/executions",
        json={
            "company_ids": [cid],
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error"] == "credential_missing_or_expired"
    assert detail["company_ids"] == [cid]


def test_post_credencial_vencida_422(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid, credential_expired=True)
    resp = client.post(
        "/executions",
        json={
            "company_ids": [cid],
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "credential_missing_or_expired"


def test_post_period_invalido_422(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    resp = client.post(
        "/executions",
        json={
            "company_ids": [cid],
            "period_start": "2026-03-01",
            "period_end": "2026-02-01",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


def test_viewer_403_post_mas_200_get(client) -> None:
    tid, _, owner_token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    _, viewer_token = _add_user(tid, email="viewer@acme.test", role="viewer")

    # Owner cria uma execution para o viewer poder GET.
    resp = client.post(
        "/executions",
        json={
            "company_ids": [cid],
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_auth(owner_token),
    )
    eid = resp.json()["created"][0]["execution_id"]

    # Viewer no POST -> 403.
    resp = client.post(
        "/executions",
        json={
            "company_ids": [cid],
            "period_start": "2026-02-01",
            "period_end": "2026-02-28",
        },
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 403

    # Viewer no GET -> 200.
    assert client.get(f"/executions/{eid}", headers=_auth(viewer_token)).status_code == 200


def test_operator_pode_disparar(client) -> None:
    tid, _, _ = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    _, op_token = _add_user(tid, email="op@acme.test", role="operator")
    resp = client.post(
        "/executions",
        json={
            "company_ids": [cid],
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_auth(op_token),
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Redis indisponivel
# ---------------------------------------------------------------------------


def test_redis_offline_antes_do_insert_502_sem_tocar_db(client, fake_redis) -> None:
    """Redis offline: 502 e zero executions criadas."""
    from api import queue as queue_mod
    from api.queue import QueueError

    class OfflineRedis:
        def ping(self):
            raise QueueError("redis offline")

    # Substitui so o cliente; mantem o RQ Queue real (nao vai ser usado).
    queue_mod.set_queue_client_for_tests(OfflineRedis(), None)

    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)

    resp = client.post(
        "/executions",
        json={
            "company_ids": [cid],
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 502
    assert "fila" in resp.json()["detail"]

    # Nada foi gravado em executions.
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        count = session.execute(
            text("SELECT COUNT(*) AS n FROM executions")
        ).one().n
    assert count == 0


def test_enqueue_falha_no_meio_marca_execution_como_failed(client, fake_redis) -> None:
    """Primeiro job OK, segundo job estoura -> 1 queued + 1 failed."""
    from api import queue as queue_mod

    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid_a = _seed_company(tenant_id=tid, cnpj=VALID_CNPJ_A)
    cid_b = _seed_company(tenant_id=tid, cnpj=VALID_CNPJ_B)

    # Usa o FakeRedis real (ping funciona), mas Queue custom que falha na 2a.
    class FlakyQueue:
        def __init__(self, real):
            self.real = real
            self.calls = 0

        def enqueue(self, *args, **kwargs):
            self.calls += 1
            if self.calls >= 2:
                raise RuntimeError("enqueue falhou (simulado)")
            return self.real.enqueue(*args, **kwargs)

    real_q = rq.Queue(name="nfse-executions-test", connection=fake_redis)
    queue_mod.set_queue_client_for_tests(fake_redis, FlakyQueue(real_q))

    resp = client.post(
        "/executions",
        json={
            "company_ids": [cid_a, cid_b],
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    statuses = sorted(item["status"] for item in body["created"])
    assert statuses == ["failed", "queued"]

    failed = next(i for i in body["created"] if i["status"] == "failed")
    assert failed["job_id"] is None
    assert failed["enqueue_error"] == "enqueue_failed"

    # GET do failed deve refletir error_summary.
    from_db = client.get(
        f"/executions/{failed['execution_id']}", headers=_auth(token)
    ).json()
    assert from_db["status"] == "failed"
    assert from_db["error_summary"] == "enqueue_failed"
    assert from_db["finished_at"] is not None


# ===========================================================================
# API-08: GET /executions, GET /executions/{id}/items, GET /companies/{id}/executions
# ===========================================================================


def _seed_execution_directly(
    *,
    tenant_id: str,
    company_id: str,
    status_: str = "succeeded",
    started_at_sql: str = "now() - interval '1 day'",
    items_total: int = 0,
    items_ok: int = 0,
    items_fail: int = 0,
) -> str:
    """Insere uma execution direto no DB (admin), sem passar pela fila.

    Permite testar a listagem com mistura de status/started_at controlada.
    """
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        row = session.execute(
            text(
                f"""
                INSERT INTO executions (
                    tenant_id, company_id, trigger,
                    period_start, period_end, status,
                    started_at, finished_at,
                    items_total, items_ok, items_fail
                ) VALUES (
                    :tid, :cid, 'manual',
                    DATE '2026-01-01', DATE '2026-01-31', :st,
                    {started_at_sql},
                    CASE WHEN :st IN ('succeeded','failed','partial','cancelled')
                         THEN now() ELSE NULL END,
                    :it, :iok, :ifa
                )
                RETURNING id
                """
            ),
            {
                "tid": tenant_id,
                "cid": company_id,
                "st": status_,
                "it": items_total,
                "iok": items_ok,
                "ifa": items_fail,
            },
        ).one()
    return str(row.id)


def _seed_execution_item(
    *,
    tenant_id: str,
    execution_id: str,
    nsu: int | None,
    status_: str = "ok",
    chave_nfse: str | None = None,
    cnpj_emitente: str | None = VALID_CNPJ_A,
) -> str:
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        row = session.execute(
            text(
                """
                INSERT INTO execution_items (
                    tenant_id, execution_id, nsu, chave_nfse,
                    cnpj_emitente, status
                ) VALUES (:tid, :eid, :nsu, :chave, :cnpj_emitente, :st)
                RETURNING id
                """
            ),
            {
                "tid": tenant_id,
                "eid": execution_id,
                "nsu": nsu,
                "chave": chave_nfse,
                "cnpj_emitente": cnpj_emitente,
                "st": status_,
            },
        ).one()
    return str(row.id)


def test_list_executions_feliz_e_ordenacao(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid_a = _seed_company(tenant_id=tid, cnpj=VALID_CNPJ_A)
    cid_b = _seed_company(tenant_id=tid, cnpj=VALID_CNPJ_B)
    eid_old = _seed_execution_directly(
        tenant_id=tid,
        company_id=cid_a,
        started_at_sql="now() - interval '3 days'",
    )
    eid_new = _seed_execution_directly(
        tenant_id=tid,
        company_id=cid_b,
        started_at_sql="now() - interval '1 hour'",
    )
    eid_queued = _seed_execution_directly(
        tenant_id=tid,
        company_id=cid_a,
        status_="queued",
        started_at_sql="NULL",
    )

    resp = client.get("/executions", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 20
    # Ordenacao: started_at DESC NULLS LAST -> recente, antigo, queued.
    ids = [item["id"] for item in body["items"]]
    assert ids == [eid_new, eid_old, eid_queued]


def test_list_executions_filtra_por_company(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid_a = _seed_company(tenant_id=tid, cnpj=VALID_CNPJ_A)
    cid_b = _seed_company(tenant_id=tid, cnpj=VALID_CNPJ_B)
    _seed_execution_directly(tenant_id=tid, company_id=cid_a)
    _seed_execution_directly(tenant_id=tid, company_id=cid_a)
    _seed_execution_directly(tenant_id=tid, company_id=cid_b)

    resp = client.get(
        f"/executions?company_id={cid_a}", headers=_auth(token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert all(item["company_id"] == cid_a for item in body["items"])


def test_list_executions_filtra_por_status(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    _seed_execution_directly(tenant_id=tid, company_id=cid, status_="succeeded")
    _seed_execution_directly(tenant_id=tid, company_id=cid, status_="failed")
    _seed_execution_directly(tenant_id=tid, company_id=cid, status_="failed")

    resp = client.get("/executions?status=failed", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {item["status"] for item in body["items"]} == {"failed"}


def test_list_executions_filtra_por_periodo_started_at(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    _seed_execution_directly(
        tenant_id=tid,
        company_id=cid,
        started_at_sql="TIMESTAMPTZ '2026-01-10 12:00:00+00'",
    )
    _seed_execution_directly(
        tenant_id=tid,
        company_id=cid,
        started_at_sql="TIMESTAMPTZ '2026-02-15 12:00:00+00'",
    )
    _seed_execution_directly(
        tenant_id=tid,
        company_id=cid,
        started_at_sql="TIMESTAMPTZ '2026-03-20 12:00:00+00'",
    )

    resp = client.get(
        "/executions"
        "?from=2026-02-01T00:00:00Z"
        "&to=2026-03-01T00:00:00Z",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["started_at"].startswith("2026-02-15")


def test_list_executions_pagina_server_side(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    # 5 execucoes com started_at decrescente para ordem deterministica.
    ids = []
    for i in range(5):
        ids.append(
            _seed_execution_directly(
                tenant_id=tid,
                company_id=cid,
                started_at_sql=f"TIMESTAMPTZ '2026-01-0{i + 1} 12:00:00+00'",
            )
        )
    # ids[0] = mais antigo (01), ids[4] = mais recente (05).

    resp1 = client.get(
        "/executions?page=1&page_size=2", headers=_auth(token)
    )
    resp2 = client.get(
        "/executions?page=2&page_size=2", headers=_auth(token)
    )
    resp3 = client.get(
        "/executions?page=3&page_size=2", headers=_auth(token)
    )
    assert resp1.json()["total"] == 5
    assert [i["id"] for i in resp1.json()["items"]] == [ids[4], ids[3]]
    assert [i["id"] for i in resp2.json()["items"]] == [ids[2], ids[1]]
    assert [i["id"] for i in resp3.json()["items"]] == [ids[0]]


def test_list_executions_cross_tenant_isolado_via_rls(client) -> None:
    tid_a, _, token_a = _seed_tenant(slug="a", email="a@a.test")
    tid_b, _, token_b = _seed_tenant(slug="b", email="b@b.test")
    cid_a = _seed_company(tenant_id=tid_a, cnpj=VALID_CNPJ_A)
    cid_b = _seed_company(tenant_id=tid_b, cnpj=VALID_CNPJ_B)
    _seed_execution_directly(tenant_id=tid_a, company_id=cid_a)
    _seed_execution_directly(tenant_id=tid_a, company_id=cid_a)
    _seed_execution_directly(tenant_id=tid_b, company_id=cid_b)

    body_a = client.get("/executions", headers=_auth(token_a)).json()
    body_b = client.get("/executions", headers=_auth(token_b)).json()
    assert body_a["total"] == 2
    assert body_b["total"] == 1


def test_list_executions_viewer_pode_ler(client) -> None:
    tid, _, _ = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    _seed_execution_directly(tenant_id=tid, company_id=cid)
    _, viewer_token = _add_user(tid, email="v@acme.test", role="viewer")

    resp = client.get("/executions", headers=_auth(viewer_token))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_companies_executions_atalho_feliz(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid_a = _seed_company(tenant_id=tid, cnpj=VALID_CNPJ_A)
    cid_b = _seed_company(tenant_id=tid, cnpj=VALID_CNPJ_B)
    _seed_execution_directly(tenant_id=tid, company_id=cid_a)
    _seed_execution_directly(tenant_id=tid, company_id=cid_a)
    _seed_execution_directly(tenant_id=tid, company_id=cid_b)

    resp = client.get(f"/companies/{cid_a}/executions", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {item["company_id"] for item in body["items"]} == {cid_a}


def test_companies_executions_atalho_company_inexistente_404(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    fake_cid = "00000000-0000-0000-0000-000000000000"
    resp = client.get(
        f"/companies/{fake_cid}/executions", headers=_auth(token)
    )
    assert resp.status_code == 404


def test_companies_executions_atalho_cross_tenant_404(client) -> None:
    tid_a, _, _ = _seed_tenant(slug="a", email="a@a.test")
    _, _, token_b = _seed_tenant(slug="b", email="b@b.test")
    cid_a = _seed_company(tenant_id=tid_a, cnpj=VALID_CNPJ_A)
    _seed_execution_directly(tenant_id=tid_a, company_id=cid_a)

    resp = client.get(
        f"/companies/{cid_a}/executions", headers=_auth(token_b)
    )
    assert resp.status_code == 404


def test_executions_items_feliz_e_ordenacao_por_nsu(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    eid = _seed_execution_directly(tenant_id=tid, company_id=cid)
    iid_3 = _seed_execution_item(tenant_id=tid, execution_id=eid, nsu=3)
    iid_1 = _seed_execution_item(tenant_id=tid, execution_id=eid, nsu=1)
    iid_2 = _seed_execution_item(tenant_id=tid, execution_id=eid, nsu=2)

    resp = client.get(f"/executions/{eid}/items", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["page_size"] == 50
    assert [i["id"] for i in body["items"]] == [iid_1, iid_2, iid_3]


def test_executions_items_filtra_por_status_e_nsu(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    eid = _seed_execution_directly(tenant_id=tid, company_id=cid)
    _seed_execution_item(tenant_id=tid, execution_id=eid, nsu=10, status_="ok")
    fail_id = _seed_execution_item(
        tenant_id=tid, execution_id=eid, nsu=11, status_="failed"
    )
    _seed_execution_item(
        tenant_id=tid, execution_id=eid, nsu=12, status_="failed"
    )

    body_status = client.get(
        f"/executions/{eid}/items?status=failed", headers=_auth(token)
    ).json()
    assert body_status["total"] == 2
    assert {i["status"] for i in body_status["items"]} == {"failed"}

    body_nsu = client.get(
        f"/executions/{eid}/items?nsu=11", headers=_auth(token)
    ).json()
    assert body_nsu["total"] == 1
    assert body_nsu["items"][0]["id"] == fail_id


def test_executions_items_default_emitidas_e_scope_all(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid, cnpj=VALID_CNPJ_A)
    eid = _seed_execution_directly(tenant_id=tid, company_id=cid)
    issued_id = _seed_execution_item(
        tenant_id=tid,
        execution_id=eid,
        nsu=20,
        cnpj_emitente=VALID_CNPJ_A,
    )
    _seed_execution_item(
        tenant_id=tid,
        execution_id=eid,
        nsu=21,
        cnpj_emitente=VALID_CNPJ_B,
    )
    _seed_execution_item(
        tenant_id=tid,
        execution_id=eid,
        nsu=22,
        cnpj_emitente=None,
    )

    default_body = client.get(
        f"/executions/{eid}/items", headers=_auth(token)
    ).json()
    assert default_body["total"] == 1
    assert default_body["items"][0]["id"] == issued_id

    all_body = client.get(
        f"/executions/{eid}/items?scope=all", headers=_auth(token)
    ).json()
    assert all_body["total"] == 3


def test_executions_items_cross_tenant_404(client) -> None:
    tid_a, _, _ = _seed_tenant(slug="a", email="a@a.test")
    _, _, token_b = _seed_tenant(slug="b", email="b@b.test")
    cid_a = _seed_company(tenant_id=tid_a, cnpj=VALID_CNPJ_A)
    eid = _seed_execution_directly(tenant_id=tid_a, company_id=cid_a)
    _seed_execution_item(tenant_id=tid_a, execution_id=eid, nsu=1)

    resp = client.get(f"/executions/{eid}/items", headers=_auth(token_b))
    assert resp.status_code == 404


def test_executions_items_viewer_pode_ler(client) -> None:
    tid, _, _ = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    eid = _seed_execution_directly(tenant_id=tid, company_id=cid)
    _seed_execution_item(tenant_id=tid, execution_id=eid, nsu=1)
    _, viewer_token = _add_user(tid, email="v@acme.test", role="viewer")

    resp = client.get(
        f"/executions/{eid}/items", headers=_auth(viewer_token)
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
