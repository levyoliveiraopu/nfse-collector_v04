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
