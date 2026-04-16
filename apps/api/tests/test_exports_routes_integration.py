"""Testes de integracao de `/exports` (API-15).

Requerem:
- Postgres real com migrations 0001..0017 aplicadas (`TEST_DATABASE_URL`).
- `moto` para mockar S3.
- `fakeredis` + `rq` para mockar a fila.

Cobertura:
- POST /exports feliz: insere linha `queued` e enfileira job.
- POST /exports viewer -> 403.
- POST /exports operator -> 201.
- POST /exports company cross-tenant -> 422 (`company_not_found`).
- POST /exports period invalido -> 422 (Pydantic).
- POST /exports Redis offline -> 502 sem tocar o DB.
- POST /exports enqueue estoura -> `failed` + `enqueue_error=enqueue_failed`.
- GET /exports/{id} antes de concluir: sem download_url.
- GET /exports/{id} cross-tenant -> 404.
- GET /exports/{id} em `status='ready'`: gera URL pre-assinada e audita.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL nao definida — pulando integracao Postgres.",
)

fakeredis = pytest.importorskip("fakeredis")
rq = pytest.importorskip("rq")
moto = pytest.importorskip("moto")
from moto import mock_aws  # noqa: E402


_TEST_BUCKET = "nfse-saas-test-exports"


@pytest.fixture()
def env_setup():
    os.environ["API_DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ.setdefault("API_JWT_SECRET", "integration-test-secret")
    os.environ.setdefault("API_ENVIRONMENT", "development")
    os.environ.setdefault("API_LOGIN_RATE_LIMIT", "1000/minute")
    os.environ.setdefault("API_REDIS_URL", "redis://fake/0")
    os.environ["S3_BUCKET"] = _TEST_BUCKET
    os.environ["S3_REGION"] = "us-east-1"
    os.environ["S3_KEY_ID"] = "test-key"
    os.environ["S3_APPLICATION_KEY"] = "test-secret"
    os.environ.pop("S3_ENDPOINT", None)
    os.environ["S3_FORCE_PATH_STYLE"] = "true"

    from api import config as config_module
    from api import storage as storage_module
    from api.db import reset_engine_for_tests
    from api.queue import reset_queue_client_for_tests

    config_module.get_settings.cache_clear()  # type: ignore[attr-defined]
    storage_module.reset_client_for_tests()
    reset_engine_for_tests()
    reset_queue_client_for_tests()
    yield
    storage_module.reset_client_for_tests()
    reset_engine_for_tests()
    reset_queue_client_for_tests()


@pytest.fixture()
def fake_redis():
    return fakeredis.FakeStrictRedis()


@pytest.fixture()
def client(env_setup, fake_redis):
    from api import queue as queue_mod
    from api import storage as storage_module
    from api.db import get_admin_session
    from api.main import create_app
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    with get_admin_session() as session:
        session.execute(
            text(
                "TRUNCATE audit_logs, exports, execution_items, executions, "
                "files, company_credentials, companies, refresh_tokens, "
                "tenant_users, users, subscriptions, tenants, plans CASCADE"
            )
        )

    q = rq.Queue(name="nfse-exports-test", connection=fake_redis)
    queue_mod.set_queue_client_for_tests(fake_redis, q)

    with mock_aws():
        s3 = storage_module._get_s3_client()
        s3.create_bucket(Bucket=_TEST_BUCKET)
        app = create_app()
        with TestClient(app) as c:
            yield c


# ---------------------------------------------------------------------------
# Fixtures de seed
# ---------------------------------------------------------------------------


def _seed_tenant(*, slug: str, email: str, role: str = "owner") -> tuple[str, str, str]:
    from api.db import get_admin_session
    from api.security.jwt import create_access_token
    from sqlalchemy import text

    with get_admin_session() as session:
        trow = session.execute(
            text("INSERT INTO tenants (name, slug) VALUES (:n, :s) RETURNING id"),
            {"n": slug.title(), "s": slug},
        ).one()
        tid = str(trow.id)
        urow = session.execute(
            text(
                "INSERT INTO users (email, password_hash, name, status) "
                "VALUES (:e, 'x', :n, 'active') RETURNING id"
            ),
            {"e": email, "n": email.split("@")[0]},
        ).one()
        uid = str(urow.id)
        session.execute(
            text(
                "INSERT INTO tenant_users (tenant_id, user_id, role, accepted_at) "
                "VALUES (:t, :u, :r, now())"
            ),
            {"t": tid, "u": uid, "r": role},
        )
    token = create_access_token(user_id=uid, tenant_id=tid, role=role)
    return tid, uid, token


def _add_user(tid: str, *, email: str, role: str) -> tuple[str, str]:
    from api.db import get_admin_session
    from api.security.jwt import create_access_token
    from sqlalchemy import text

    with get_admin_session() as session:
        urow = session.execute(
            text(
                "INSERT INTO users (email, password_hash, name, status) "
                "VALUES (:e, 'x', :n, 'active') RETURNING id"
            ),
            {"e": email, "n": email.split("@")[0]},
        ).one()
        uid = str(urow.id)
        session.execute(
            text(
                "INSERT INTO tenant_users (tenant_id, user_id, role, accepted_at) "
                "VALUES (:t, :u, :r, now())"
            ),
            {"t": tid, "u": uid, "r": role},
        )
    return uid, create_access_token(user_id=uid, tenant_id=tid, role=role)


def _seed_company(tid: str, cnpj: str = "11222333000181") -> str:
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        row = session.execute(
            text(
                "INSERT INTO companies "
                "(tenant_id, cnpj, razao_social, municipio_ibge, uf, status) "
                "VALUES (:t, :c, 'Acme', '3550308', 'SP', 'active') RETURNING id"
            ),
            {"t": tid, "c": cnpj},
        ).one()
    return str(row.id)


def _insert_ready_export(
    *, tid: str, uid: str, cid: str, file_object_key: str
) -> tuple[str, str]:
    """Insere diretamente uma linha `exports` em `status='ready'` + file."""
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        frow = session.execute(
            text(
                "INSERT INTO files "
                "(tenant_id, kind, object_key, bytes, checksum_sha256, expires_at) "
                "VALUES (:t, 'export', :k, 42, :c, now() + interval '30 days') "
                "RETURNING id"
            ),
            {"t": tid, "k": file_object_key, "c": "a" * 64},
        ).one()
        fid = str(frow.id)
        erow = session.execute(
            text(
                """
                INSERT INTO exports (
                    tenant_id, company_id, requested_by_user_id,
                    kind, period_start, period_end, status,
                    file_id, items_count, total_bytes,
                    started_at, finished_at
                ) VALUES (
                    :t, :c, :u, 'zip_xml',
                    '2026-01-01', '2026-01-31', 'ready',
                    :f, 3, 42,
                    now() - interval '5 min', now()
                )
                RETURNING id
                """
            ),
            {"t": tid, "c": cid, "u": uid, "f": fid},
        ).one()
    return str(erow.id), fid


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /exports
# ---------------------------------------------------------------------------


def test_post_export_happy_path(client, fake_redis) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="owner@acme.test")
    cid = _seed_company(tid)

    resp = client.post(
        "/exports",
        json={
            "company_id": cid,
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["job_id"]
    assert body["enqueue_error"] is None

    q = rq.Queue(name="nfse-exports-test", connection=fake_redis)
    assert q.count == 1
    job = q.jobs[0]
    assert job.func_name == "worker_core.jobs.build_export"
    assert str(job.args[0]) == body["export_id"]


def test_post_export_viewer_403(client) -> None:
    tid, _, _ = _seed_tenant(slug="a", email="a@a.test")
    cid = _seed_company(tid)
    _, viewer_token = _add_user(tid, email="v@a.test", role="viewer")
    resp = client.post(
        "/exports",
        json={
            "company_id": cid,
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 403


def test_post_export_operator_pode(client) -> None:
    tid, _, _ = _seed_tenant(slug="a", email="a@a.test")
    cid = _seed_company(tid)
    _, op_token = _add_user(tid, email="op@a.test", role="operator")
    resp = client.post(
        "/exports",
        json={
            "company_id": cid,
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_auth(op_token),
    )
    assert resp.status_code == 201


def test_post_company_outro_tenant_422(client) -> None:
    tid_a, _, _ = _seed_tenant(slug="a", email="a@a.test")
    _, _, token_b = _seed_tenant(slug="b", email="b@b.test")
    cid_a = _seed_company(tid_a)
    resp = client.post(
        "/exports",
        json={
            "company_id": cid_a,
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_auth(token_b),
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "company_not_found"


def test_post_period_invalido_422(client) -> None:
    tid, _, token = _seed_tenant(slug="a", email="a@a.test")
    cid = _seed_company(tid)
    resp = client.post(
        "/exports",
        json={
            "company_id": cid,
            "period_start": "2026-03-01",
            "period_end": "2026-02-01",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 422


def test_redis_offline_502_sem_tocar_db(client, fake_redis) -> None:
    from api import queue as queue_mod
    from api.queue import QueueError

    class OfflineRedis:
        def ping(self):
            raise QueueError("redis offline")

    queue_mod.set_queue_client_for_tests(OfflineRedis(), None)
    tid, _, token = _seed_tenant(slug="a", email="a@a.test")
    cid = _seed_company(tid)
    resp = client.post(
        "/exports",
        json={
            "company_id": cid,
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 502

    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        n = session.execute(text("SELECT COUNT(*) AS n FROM exports")).one().n
    assert n == 0


def test_enqueue_falha_marca_failed(client, fake_redis) -> None:
    from api import queue as queue_mod

    class FlakyQueue:
        def enqueue(self, *args, **kwargs):
            raise RuntimeError("enqueue falhou simulado")

    queue_mod.set_queue_client_for_tests(fake_redis, FlakyQueue())

    tid, _, token = _seed_tenant(slug="a", email="a@a.test")
    cid = _seed_company(tid)
    resp = client.post(
        "/exports",
        json={
            "company_id": cid,
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "failed"
    assert body["job_id"] is None
    assert body["enqueue_error"] == "enqueue_failed"

    got = client.get(f"/exports/{body['export_id']}", headers=_auth(token))
    assert got.status_code == 200
    detail = got.json()
    assert detail["status"] == "failed"
    assert detail["error_code"] == "enqueue_failed"
    assert detail["finished_at"] is not None


# ---------------------------------------------------------------------------
# GET /exports/{id}
# ---------------------------------------------------------------------------


def test_get_queued_sem_download_url(client) -> None:
    tid, _, token = _seed_tenant(slug="a", email="a@a.test")
    cid = _seed_company(tid)
    resp = client.post(
        "/exports",
        json={
            "company_id": cid,
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_auth(token),
    )
    eid = resp.json()["export_id"]
    got = client.get(f"/exports/{eid}", headers=_auth(token))
    assert got.status_code == 200
    body = got.json()
    assert body["status"] == "queued"
    assert body["download_url"] is None
    assert body["expires_in"] is None
    assert body["file_id"] is None


def test_get_cross_tenant_404(client) -> None:
    tid_a, _, token_a = _seed_tenant(slug="a", email="a@a.test")
    _, _, token_b = _seed_tenant(slug="b", email="b@b.test")
    cid_a = _seed_company(tid_a)
    resp = client.post(
        "/exports",
        json={
            "company_id": cid_a,
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_auth(token_a),
    )
    eid = resp.json()["export_id"]
    assert client.get(f"/exports/{eid}", headers=_auth(token_b)).status_code == 404


def test_get_ready_emite_url_e_audita(client) -> None:
    tid, uid, token = _seed_tenant(slug="a", email="a@a.test")
    cid = _seed_company(tid)
    object_key = f"tenants-exports/{tid}/{uuid.uuid4()}.zip"
    eid, fid = _insert_ready_export(
        tid=tid, uid=uid, cid=cid, file_object_key=object_key
    )
    resp = client.get(f"/exports/{eid}", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ready"
    assert body["file_id"] == fid
    assert body["expires_in"] == 3600
    assert body["download_url"].startswith("http")
    assert "X-Amz-Signature" in body["download_url"]

    # Audit gravado com metadata publica, sem a URL.
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        rows = session.execute(
            text(
                "SELECT action, metadata FROM audit_logs "
                "WHERE resource_type = 'export' AND resource_id = :rid"
            ),
            {"rid": eid},
        ).all()
    assert len(rows) == 1
    assert rows[0].action == "export.download_url"
    md = rows[0].metadata
    assert md["export_id"] == eid
    assert md["file_id"] == fid
    assert md["object_key"] == object_key
    assert md["expires_in"] == 3600
    assert "url" not in md
    assert body["download_url"] not in json.dumps(md)


def test_get_viewer_pode_consultar(client) -> None:
    tid, uid, _ = _seed_tenant(slug="a", email="a@a.test")
    cid = _seed_company(tid)
    _, viewer_token = _add_user(tid, email="v@a.test", role="viewer")
    object_key = f"tenants-exports/{tid}/{uuid.uuid4()}.zip"
    eid, _ = _insert_ready_export(
        tid=tid, uid=uid, cid=cid, file_object_key=object_key
    )
    resp = client.get(f"/exports/{eid}", headers=_auth(viewer_token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"
