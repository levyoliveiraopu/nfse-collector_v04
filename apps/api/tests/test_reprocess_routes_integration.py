"""Testes de integracao de `/reprocess` (API-10).

Exige Postgres real com migrations aplicadas (mesmo padrao de
API-02/03/05/07/08). Pulados quando `TEST_DATABASE_URL` nao estiver
definida. A fila Redis e substituida por `fakeredis`, portanto nao
e necessario Redis rodando.

Cobertura:
- 3 escopos felizes: items, nsus, period.
- Items cross-tenant -> 422 com ids faltantes.
- Items agrupam por (company, period) distintas -> N executions filhas.
- Company inexistente -> 422 (`companies_not_found`).
- Company sem credencial ativa -> 422.
- Viewer -> 403 no POST, 200 no GET.
- Operator pode disparar.
- Redis offline -> 502 sem criar reprocess_job.
- Enqueue falha no meio -> execution filha marcada `failed`; se todas
  falharem, o proprio reprocess_job vira `failed` com error_summary.
- GET: cross-tenant 404; progress agregado reflete estados mistos.
- GET: effective_status nos cenarios (running, succeeded, partial,
  failed).
- Audit log `reprocess.create` gravado sem vazar scope sensivel.
"""

from __future__ import annotations

import json
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
    return fakeredis.FakeStrictRedis()


@pytest.fixture()
def client(env_setup, fake_redis):
    from api import queue as queue_mod
    from api.db import get_admin_session
    from api.main import create_app
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    with get_admin_session() as session:
        session.execute(
            text(
                "TRUNCATE audit_logs, reprocess_jobs, execution_items, executions, "
                "company_credentials, companies, refresh_tokens, "
                "tenant_users, users, subscriptions, tenants, plans CASCADE"
            )
        )

    q = rq.Queue(name="nfse-executions-test", connection=fake_redis)
    queue_mod.set_queue_client_for_tests(fake_redis, q)

    app = create_app()
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Seeds
# ---------------------------------------------------------------------------


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


def _add_user(tenant_id: str, *, email: str, role: str) -> tuple[str, str]:
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
    *,
    tenant_id: str,
    cnpj: str = VALID_CNPJ_A,
    with_credential: bool = True,
) -> str:
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
            session.execute(
                text(
                    """
                    INSERT INTO company_credentials (
                        tenant_id, company_id, type, pfx_object_key,
                        pfx_password_ciphertext, cert_fingerprint,
                        cert_not_before, cert_not_after, status
                    ) VALUES (
                        :tid, :cid, 'pfx_a1', 'stub-key',
                        decode('01', 'hex'), 'stub-fp',
                        now() - interval '30 days',
                        now() + interval '365 days',
                        'active'
                    )
                    """
                ),
                {"tid": tenant_id, "cid": cid},
            )

    return cid


def _seed_execution(
    *,
    tenant_id: str,
    company_id: str,
    status_: str = "failed",
    period_start: str = "2026-01-01",
    period_end: str = "2026-01-31",
    trigger: str = "manual",
) -> str:
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        row = session.execute(
            text(
                """
                INSERT INTO executions (
                    tenant_id, company_id, trigger,
                    period_start, period_end, status, started_at, finished_at
                ) VALUES (
                    :tid, :cid, :trig,
                    CAST(:ps AS date), CAST(:pe AS date), :st,
                    now() - interval '1 day', now()
                )
                RETURNING id
                """
            ),
            {
                "tid": tenant_id,
                "cid": company_id,
                "trig": trigger,
                "ps": period_start,
                "pe": period_end,
                "st": status_,
            },
        ).one()
    return str(row.id)


def _seed_item(
    *,
    tenant_id: str,
    execution_id: str,
    nsu: Optional[int] = None,
    status_: str = "failed",
    chave_nfse: Optional[str] = None,
    data_emissao: Optional[str] = None,
) -> str:
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        row = session.execute(
            text(
                """
                INSERT INTO execution_items (
                    tenant_id, execution_id, nsu, chave_nfse,
                    data_emissao, status
                ) VALUES (
                    :tid, :eid, :nsu, :chave,
                    CAST(:de AS timestamptz), :st
                )
                RETURNING id
                """
            ),
            {
                "tid": tenant_id,
                "eid": execution_id,
                "nsu": nsu,
                "chave": chave_nfse,
                "de": data_emissao,
                "st": status_,
            },
        ).one()
    return str(row.id)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# POST /reprocess — escopo 1 (items)
# ===========================================================================


def test_reprocess_por_items_agrupa_por_execution(client, fake_redis) -> None:
    """3 items em 2 executions distintas -> 2 executions filhas."""
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    eid_jan = _seed_execution(
        tenant_id=tid,
        company_id=cid,
        period_start="2026-01-01",
        period_end="2026-01-31",
    )
    eid_feb = _seed_execution(
        tenant_id=tid,
        company_id=cid,
        period_start="2026-02-01",
        period_end="2026-02-28",
    )
    item1 = _seed_item(tenant_id=tid, execution_id=eid_jan, nsu=10)
    item2 = _seed_item(tenant_id=tid, execution_id=eid_jan, nsu=11)
    item3 = _seed_item(tenant_id=tid, execution_id=eid_feb, nsu=20)

    resp = client.post(
        "/reprocess",
        json={"execution_item_ids": [item1, item2, item3]},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["scope"] == {
        "kind": "items",
        "execution_item_ids": [item1, item2, item3],
    }
    # 2 executions filhas (jan + fev).
    assert len(body["result_execution_ids"]) == 2
    assert len(body["created_executions"]) == 2
    periods = sorted(
        (c["period_start"], c["period_end"]) for c in body["created_executions"]
    )
    assert periods == [
        ("2026-01-01", "2026-01-31"),
        ("2026-02-01", "2026-02-28"),
    ]
    for child in body["created_executions"]:
        assert child["status"] == "queued"
        assert child["job_id"]

    # N jobs na fila fake.
    q = rq.Queue(name="nfse-executions-test", connection=fake_redis)
    assert q.count == 2

    # As executions filhas tem trigger='reprocess'.
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        rows = session.execute(
            text(
                "SELECT trigger FROM executions "
                "WHERE id = ANY(:ids) ORDER BY trigger"
            ),
            {"ids": body["result_execution_ids"]},
        ).all()
    triggers = [r.trigger for r in rows]
    assert triggers == ["reprocess", "reprocess"]


def test_reprocess_por_items_cross_tenant_422(client) -> None:
    tid_a, _, _ = _seed_tenant(slug="a", email="a@a.test")
    _, _, token_b = _seed_tenant(slug="b", email="b@b.test")
    cid = _seed_company(tenant_id=tid_a)
    eid = _seed_execution(tenant_id=tid_a, company_id=cid)
    item = _seed_item(tenant_id=tid_a, execution_id=eid, nsu=1)

    resp = client.post(
        "/reprocess",
        json={"execution_item_ids": [item]},
        headers=_auth(token_b),
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error"] == "execution_items_not_found"
    assert detail["missing"] == [item]


def test_reprocess_por_items_id_inexistente_422(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    from uuid import uuid4

    ghost = str(uuid4())
    resp = client.post(
        "/reprocess",
        json={"execution_item_ids": [ghost]},
        headers=_auth(token),
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "execution_items_not_found"


# ===========================================================================
# POST /reprocess — escopo 2 (nsus)
# ===========================================================================


def test_reprocess_por_nsus_infere_periodo_dos_items(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    eid = _seed_execution(tenant_id=tid, company_id=cid)
    _seed_item(
        tenant_id=tid,
        execution_id=eid,
        nsu=100,
        data_emissao="2026-01-05T10:00:00+00",
    )
    _seed_item(
        tenant_id=tid,
        execution_id=eid,
        nsu=101,
        data_emissao="2026-01-20T10:00:00+00",
    )

    resp = client.post(
        "/reprocess",
        json={"company_id": cid, "nsus": [100, 101]},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # 1 execution filha cobrindo 2026-01-05..2026-01-20.
    assert len(body["created_executions"]) == 1
    child = body["created_executions"][0]
    assert child["period_start"] == "2026-01-05"
    assert child["period_end"] == "2026-01-20"
    assert child["company_id"] == cid
    assert body["scope"] == {
        "kind": "nsus",
        "company_id": cid,
        "nsus": [100, 101],
    }


def test_reprocess_por_nsus_sem_match_usa_today_fallback(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)

    resp = client.post(
        "/reprocess",
        json={"company_id": cid, "nsus": [999_999]},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body["created_executions"]) == 1
    child = body["created_executions"][0]
    # Fallback: periodo = [today, today].
    assert child["period_start"] == child["period_end"]
    assert child["period_start"] == date.today().isoformat()


# ===========================================================================
# POST /reprocess — escopo 3 (period)
# ===========================================================================


def test_reprocess_por_period_feliz(client, fake_redis) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)

    resp = client.post(
        "/reprocess",
        json={
            "company_id": cid,
            "period": {"start": "2026-03-01", "end": "2026-03-31"},
            "statuses": ["failed"],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body["created_executions"]) == 1
    assert body["created_executions"][0]["period_start"] == "2026-03-01"
    assert body["created_executions"][0]["period_end"] == "2026-03-31"
    assert body["scope"]["statuses"] == ["failed"]

    q = rq.Queue(name="nfse-executions-test", connection=fake_redis)
    assert q.count == 1


def test_reprocess_period_end_menor_que_start_422(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)

    resp = client.post(
        "/reprocess",
        json={
            "company_id": cid,
            "period": {"start": "2026-03-31", "end": "2026-03-01"},
        },
        headers=_auth(token),
    )
    assert resp.status_code == 422


# ===========================================================================
# Validacao de companies / credenciais
# ===========================================================================


def test_reprocess_company_inexistente_422(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    from uuid import uuid4

    resp = client.post(
        "/reprocess",
        json={
            "company_id": str(uuid4()),
            "period": {"start": "2026-01-01", "end": "2026-01-31"},
        },
        headers=_auth(token),
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "companies_not_found"


def test_reprocess_company_sem_credencial_422(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid, with_credential=False)

    resp = client.post(
        "/reprocess",
        json={
            "company_id": cid,
            "period": {"start": "2026-01-01", "end": "2026-01-31"},
        },
        headers=_auth(token),
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "credential_missing_or_expired"


# ===========================================================================
# RBAC
# ===========================================================================


def test_viewer_403_post_mas_200_get(client) -> None:
    tid, _, owner_token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    _, viewer_token = _add_user(tid, email="viewer@acme.test", role="viewer")

    resp = client.post(
        "/reprocess",
        json={
            "company_id": cid,
            "period": {"start": "2026-01-01", "end": "2026-01-31"},
        },
        headers=_auth(owner_token),
    )
    assert resp.status_code == 201
    rid = resp.json()["id"]

    # Viewer no POST -> 403.
    resp = client.post(
        "/reprocess",
        json={
            "company_id": cid,
            "period": {"start": "2026-02-01", "end": "2026-02-28"},
        },
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 403

    # Viewer no GET -> 200.
    assert client.get(f"/reprocess/{rid}", headers=_auth(viewer_token)).status_code == 200


def test_operator_pode_disparar(client) -> None:
    tid, _, _ = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    _, op_token = _add_user(tid, email="op@acme.test", role="operator")

    resp = client.post(
        "/reprocess",
        json={
            "company_id": cid,
            "period": {"start": "2026-01-01", "end": "2026-01-31"},
        },
        headers=_auth(op_token),
    )
    assert resp.status_code == 201


# ===========================================================================
# Redis indisponivel / enqueue falha
# ===========================================================================


def test_redis_offline_502_sem_tocar_db(client) -> None:
    from api import queue as queue_mod
    from api.queue import QueueError

    class OfflineRedis:
        def ping(self):
            raise QueueError("redis offline")

    queue_mod.set_queue_client_for_tests(OfflineRedis(), None)

    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)

    resp = client.post(
        "/reprocess",
        json={
            "company_id": cid,
            "period": {"start": "2026-01-01", "end": "2026-01-31"},
        },
        headers=_auth(token),
    )
    assert resp.status_code == 502

    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        n = session.execute(
            text("SELECT COUNT(*) AS n FROM reprocess_jobs")
        ).one().n
    assert n == 0


def test_enqueue_falha_em_todas_marca_reprocess_como_failed(
    client, fake_redis
) -> None:
    """Quando todas as executions filhas falham no enqueue, o job-pai vira failed."""
    from api import queue as queue_mod

    class AlwaysFailQueue:
        def enqueue(self, *args, **kwargs):
            raise RuntimeError("enqueue sempre falha")

    queue_mod.set_queue_client_for_tests(fake_redis, AlwaysFailQueue())

    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    eid = _seed_execution(tenant_id=tid, company_id=cid)
    item = _seed_item(tenant_id=tid, execution_id=eid, nsu=1)

    resp = client.post(
        "/reprocess",
        json={"execution_item_ids": [item]},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    # Envelope do job-pai reflete failure total.
    assert body["status"] == "failed"
    assert body["error_summary"] == "enqueue_failed_all"
    assert body["finished_at"] is not None
    # Execution filha marcada failed.
    assert body["created_executions"][0]["status"] == "failed"
    assert body["created_executions"][0]["enqueue_error"] == "enqueue_failed"


# ===========================================================================
# GET /reprocess/{id}
# ===========================================================================


def test_get_cross_tenant_404(client) -> None:
    tid_a, _, token_a = _seed_tenant(slug="a", email="a@a.test")
    _, _, token_b = _seed_tenant(slug="b", email="b@b.test")
    cid = _seed_company(tenant_id=tid_a)

    resp = client.post(
        "/reprocess",
        json={
            "company_id": cid,
            "period": {"start": "2026-01-01", "end": "2026-01-31"},
        },
        headers=_auth(token_a),
    )
    rid = resp.json()["id"]

    assert client.get(f"/reprocess/{rid}", headers=_auth(token_b)).status_code == 404


def test_get_progress_running_quando_ha_execution_queued(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)

    resp = client.post(
        "/reprocess",
        json={
            "company_id": cid,
            "period": {"start": "2026-01-01", "end": "2026-01-31"},
        },
        headers=_auth(token),
    )
    rid = resp.json()["id"]

    got = client.get(f"/reprocess/{rid}", headers=_auth(token)).json()
    prog = got["progress"]
    assert prog["total"] == 1
    assert prog["queued"] == 1
    assert prog["effective_status"] == "running"


def test_get_progress_succeeded_quando_todas_ok(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)

    resp = client.post(
        "/reprocess",
        json={
            "company_id": cid,
            "period": {"start": "2026-01-01", "end": "2026-01-31"},
        },
        headers=_auth(token),
    )
    rid = resp.json()["id"]
    child_ids = resp.json()["result_execution_ids"]

    # Marca a execucao filha como succeeded direto no banco.
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        session.execute(
            text(
                """
                UPDATE executions
                   SET status = 'succeeded', finished_at = now(),
                       items_total = 2, items_ok = 2, items_fail = 0
                 WHERE id = ANY(:ids)
                """
            ),
            {"ids": child_ids},
        )

    got = client.get(f"/reprocess/{rid}", headers=_auth(token)).json()
    prog = got["progress"]
    assert prog["succeeded"] == 1
    assert prog["queued"] == 0
    assert prog["effective_status"] == "succeeded"


def test_get_progress_partial_mistura_sucesso_e_falha(
    client, fake_redis
) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid_a = _seed_company(tenant_id=tid, cnpj=VALID_CNPJ_A)
    cid_b = _seed_company(tenant_id=tid, cnpj=VALID_CNPJ_B)

    # Usa escopo por items com 2 executions-pai distintas em 2 companies
    # para garantir 2 executions filhas.
    eid_a = _seed_execution(tenant_id=tid, company_id=cid_a)
    eid_b = _seed_execution(tenant_id=tid, company_id=cid_b)
    item_a = _seed_item(tenant_id=tid, execution_id=eid_a, nsu=1)
    item_b = _seed_item(tenant_id=tid, execution_id=eid_b, nsu=2)

    resp = client.post(
        "/reprocess",
        json={"execution_item_ids": [item_a, item_b]},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    rid = resp.json()["id"]
    child_ids = resp.json()["result_execution_ids"]
    assert len(child_ids) == 2

    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        session.execute(
            text(
                "UPDATE executions SET status='succeeded', finished_at=now() "
                "WHERE id = :eid"
            ),
            {"eid": child_ids[0]},
        )
        session.execute(
            text(
                "UPDATE executions SET status='failed', finished_at=now() "
                "WHERE id = :eid"
            ),
            {"eid": child_ids[1]},
        )

    got = client.get(f"/reprocess/{rid}", headers=_auth(token)).json()
    prog = got["progress"]
    assert prog["succeeded"] == 1
    assert prog["failed"] == 1
    assert prog["effective_status"] == "partial"


def test_get_404_id_inexistente(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    from uuid import uuid4

    resp = client.get(f"/reprocess/{uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


# ===========================================================================
# Audit log
# ===========================================================================


def test_audit_log_registrado_sem_vazar_sensivel(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)

    resp = client.post(
        "/reprocess",
        json={
            "company_id": cid,
            "period": {"start": "2026-01-01", "end": "2026-01-31"},
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    rid = resp.json()["id"]

    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        rows = session.execute(
            text(
                "SELECT action, resource_type, resource_id, metadata "
                "FROM audit_logs WHERE resource_id = :rid"
            ),
            {"rid": rid},
        ).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "reprocess.create"
    assert row.resource_type == "reprocess_job"
    meta = row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata)
    assert meta["scope_kind"] == "period"
    assert meta["executions_count"] == 1
    assert meta["dry_run"] is False
    # Nao grava company_id nem period em audit (scope fica em reprocess_jobs.scope).
    assert "company_id" not in meta
    assert "period" not in meta


# ===========================================================================
# DoD: forca falha em 3 items, reprocessa 1 (cobertura E2E simbolica)
# ===========================================================================


def test_dod_reprocessa_1_de_3_items_falhos(client, fake_redis) -> None:
    """Forca falha em 3 items de 1 execution, reprocessa 1 via items scope.

    O worker real (API-13) que atualiza `execution_items.status` para `ok`
    apos refazer a coleta nao roda neste teste — e E2E real com Postgres
    + Redis + portal. O que provamos aqui:

    - 3 items falhos sao seedados.
    - O POST /reprocess aceita o item escolhido e cria 1 execution filha
      com trigger='reprocess' cobrindo o periodo da execution-pai.
    - 1 job entra na fila para o worker picar.
    """
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tenant_id=tid)
    eid = _seed_execution(
        tenant_id=tid,
        company_id=cid,
        period_start="2026-01-01",
        period_end="2026-01-31",
        status_="partial",
    )
    items = [
        _seed_item(tenant_id=tid, execution_id=eid, nsu=n)
        for n in (1, 2, 3)
    ]
    escolhido = items[1]

    resp = client.post(
        "/reprocess",
        json={"execution_item_ids": [escolhido]},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body["created_executions"]) == 1
    child = body["created_executions"][0]
    assert child["period_start"] == "2026-01-01"
    assert child["period_end"] == "2026-01-31"
    assert child["status"] == "queued"

    q = rq.Queue(name="nfse-executions-test", connection=fake_redis)
    assert q.count == 1
    queued_job = q.jobs[0]
    assert str(queued_job.args[0]) == child["execution_id"]


