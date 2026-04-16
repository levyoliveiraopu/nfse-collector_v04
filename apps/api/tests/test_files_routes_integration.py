"""Testes de integracao de `/files` (API-11).

Requerem:
- Postgres real com migrations 0001..0016 aplicadas (`TEST_DATABASE_URL`).
- `moto` para gerar URL pre-assinada (bucket fake).

Cobertura:
- GET /files lista arquivos do tenant atual (RLS).
- GET /files filtra por `kind`, `company` (via JOIN em executions) e
  intervalo `from`/`to`.
- GET /files paginacao (`page`/`page_size`) e total correto.
- GET /files cross-tenant devolve 0 linhas (RLS).
- GET /files/{id}/url gera URL assinada com `expires_in=3600`.
- GET /files/{id}/url cross-tenant -> 404 (DoD do ticket).
- GET /files/{id}/url audita em `audit_logs` com action
  `file.download_url`, metadata publica e sem a URL em claro (DoD).
- Viewer consegue listar e gerar URL (matriz RBAC).
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL nao definida — pulando integracao Postgres.",
)

moto = pytest.importorskip("moto")
from moto import mock_aws  # noqa: E402


_TEST_BUCKET = "nfse-saas-test"


@pytest.fixture()
def env_setup():
    os.environ["API_DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ.setdefault("API_JWT_SECRET", "integration-test-secret")
    os.environ.setdefault("API_ENVIRONMENT", "development")
    os.environ.setdefault("API_LOGIN_RATE_LIMIT", "1000/minute")
    os.environ["S3_BUCKET"] = _TEST_BUCKET
    os.environ["S3_REGION"] = "us-east-1"
    os.environ["S3_KEY_ID"] = "test-key"
    os.environ["S3_APPLICATION_KEY"] = "test-secret"
    os.environ.pop("S3_ENDPOINT", None)
    os.environ["S3_FORCE_PATH_STYLE"] = "true"

    from api import config as config_module
    from api import storage as storage_module
    from api.db import reset_engine_for_tests

    config_module.get_settings.cache_clear()  # type: ignore[attr-defined]
    storage_module.reset_client_for_tests()
    reset_engine_for_tests()
    yield
    storage_module.reset_client_for_tests()
    reset_engine_for_tests()


@pytest.fixture()
def client(env_setup):
    from api.db import get_admin_session
    from api.main import create_app
    from api import storage as storage_module
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    with get_admin_session() as session:
        session.execute(
            text(
                "TRUNCATE audit_logs, files, execution_items, executions, "
                "company_credentials, companies, refresh_tokens, "
                "tenant_users, users, subscriptions, tenants, plans CASCADE"
            )
        )

    with mock_aws():
        s3 = storage_module._get_s3_client()
        s3.create_bucket(Bucket=_TEST_BUCKET)
        app = create_app()
        with TestClient(app) as c:
            yield c


def _seed_tenant(*, slug: str, email: str, role: str = "owner") -> tuple[str, str, str]:
    from api.db import get_admin_session
    from api.security.jwt import create_access_token
    from sqlalchemy import text

    with get_admin_session() as session:
        trow = session.execute(
            text("INSERT INTO tenants (name, slug) VALUES (:n, :s) RETURNING id"),
            {"n": slug.title(), "s": slug},
        ).one()
        tenant_id = str(trow.id)
        urow = session.execute(
            text(
                "INSERT INTO users (email, password_hash, name, status) "
                "VALUES (:e, 'x', :n, 'active') RETURNING id"
            ),
            {"e": email, "n": email.split("@")[0]},
        ).one()
        user_id = str(urow.id)
        session.execute(
            text(
                "INSERT INTO tenant_users (tenant_id, user_id, role, accepted_at) "
                "VALUES (:t, :u, :r, now())"
            ),
            {"t": tenant_id, "u": user_id, "r": role},
        )
    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role=role)
    return tenant_id, user_id, token


def _seed_company(*, tenant_id: str, cnpj: str = "11222333000181") -> str:
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        row = session.execute(
            text(
                """
                INSERT INTO companies (
                    tenant_id, cnpj, razao_social, municipio_ibge, uf, status
                ) VALUES (:t, :cnpj, 'Acme LTDA', '3550308', 'SP', 'active')
                RETURNING id
                """
            ),
            {"t": tenant_id, "cnpj": cnpj},
        ).one()
    return str(row.id)


def _seed_execution(*, tenant_id: str, company_id: str) -> str:
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        row = session.execute(
            text(
                """
                INSERT INTO executions (
                    tenant_id, company_id, trigger, status,
                    period_start, period_end
                ) VALUES (
                    :t, :c, 'manual', 'succeeded',
                    current_date - 1, current_date
                )
                RETURNING id
                """
            ),
            {"t": tenant_id, "c": company_id},
        ).one()
    return str(row.id)


def _seed_file(
    *,
    tenant_id: str,
    kind: str = "export",
    object_key: str | None = None,
    source_execution_id: str | None = None,
    size_bytes: int = 1024,
    created_at_sql: str | None = None,
) -> str:
    """Insere uma linha em `files` via BYPASSRLS e devolve o id."""
    from api.db import get_admin_session
    from sqlalchemy import text

    key = object_key or f"tenants/{tenant_id}/{uuid.uuid4()}.xml"
    checksum = hashlib.sha256(key.encode()).hexdigest()
    created_expr = "now()" if created_at_sql is None else created_at_sql

    with get_admin_session() as session:
        row = session.execute(
            text(
                f"""
                INSERT INTO files (
                    tenant_id, kind, object_key, bytes,
                    checksum_sha256, source_execution_id, created_at, updated_at
                ) VALUES (
                    :t, :k, :okey, :b, :csum, :seid, {created_expr}, now()
                )
                RETURNING id
                """
            ),
            {
                "t": tenant_id,
                "k": kind,
                "okey": key,
                "b": size_bytes,
                "csum": checksum,
                "seid": source_execution_id,
            },
        ).one()
    return str(row.id)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /files — lista + filtros + RLS
# ---------------------------------------------------------------------------


def test_list_files_isolado_por_tenant(client) -> None:
    tid_a, _, token_a = _seed_tenant(slug="acme", email="a@acme.test")
    tid_b, _, token_b = _seed_tenant(slug="beta", email="b@beta.test")

    _seed_file(tenant_id=tid_a, kind="export")
    _seed_file(tenant_id=tid_a, kind="nfse_xml")
    _seed_file(tenant_id=tid_b, kind="export")

    resp = client.get("/files", headers=_auth(token_a))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert {it["tenant_id"] for it in body["items"]} == {tid_a}

    resp_b = client.get("/files", headers=_auth(token_b))
    assert resp_b.json()["total"] == 1


def test_list_files_filtra_por_kind(client) -> None:
    tid, _, token = _seed_tenant(slug="acmek", email="o@k.test")
    _seed_file(tenant_id=tid, kind="export")
    _seed_file(tenant_id=tid, kind="nfse_xml")
    _seed_file(tenant_id=tid, kind="nfse_xml")

    resp = client.get("/files?kind=nfse_xml", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {it["kind"] for it in body["items"]} == {"nfse_xml"}


def test_list_files_filtra_por_company(client) -> None:
    tid, _, token = _seed_tenant(slug="acmec", email="o@c.test")
    company_a = _seed_company(tenant_id=tid, cnpj="11222333000181")
    company_b = _seed_company(tenant_id=tid, cnpj="04252011000110")
    exec_a = _seed_execution(tenant_id=tid, company_id=company_a)
    exec_b = _seed_execution(tenant_id=tid, company_id=company_b)

    file_a = _seed_file(tenant_id=tid, kind="nfse_xml", source_execution_id=exec_a)
    _seed_file(tenant_id=tid, kind="nfse_xml", source_execution_id=exec_b)
    # File sem execution associada — nao deve aparecer quando filtra por company.
    _seed_file(tenant_id=tid, kind="export", source_execution_id=None)

    resp = client.get(f"/files?company={company_a}", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == file_a


def test_list_files_filtra_por_periodo(client) -> None:
    tid, _, token = _seed_tenant(slug="acmep", email="o@p.test")
    _seed_file(
        tenant_id=tid,
        kind="export",
        created_at_sql="now() - interval '10 days'",
    )
    _seed_file(
        tenant_id=tid,
        kind="export",
        created_at_sql="now() - interval '2 days'",
    )
    _seed_file(tenant_id=tid, kind="export")  # agora

    from datetime import datetime, timedelta, timezone

    cutoff_from = datetime.now(tz=timezone.utc) - timedelta(days=5)
    resp = client.get(
        f"/files?from={cutoff_from.isoformat()}", headers=_auth(token)
    )
    assert resp.status_code == 200
    # Deixa fora o de 10 dias atras.
    assert resp.json()["total"] == 2

    cutoff_to = datetime.now(tz=timezone.utc) - timedelta(hours=1)
    resp = client.get(
        f"/files?to={cutoff_to.isoformat()}", headers=_auth(token)
    )
    # Deixa fora o de agora.
    assert resp.json()["total"] == 2


def test_list_files_paginacao(client) -> None:
    tid, _, token = _seed_tenant(slug="acmepg", email="o@pg.test")
    for _ in range(5):
        _seed_file(tenant_id=tid, kind="export")

    resp = client.get("/files?page=1&page_size=2", headers=_auth(token))
    body = resp.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2

    resp2 = client.get("/files?page=3&page_size=2", headers=_auth(token))
    body2 = resp2.json()
    assert body2["page"] == 3
    assert len(body2["items"]) == 1  # sobra 1


def test_list_files_viewer_pode_ler(client) -> None:
    tid, _, _ = _seed_tenant(slug="acmev", email="o@v.test")
    _seed_file(tenant_id=tid, kind="export")

    # Segundo user como viewer no mesmo tenant.
    from api.db import get_admin_session
    from api.security.jwt import create_access_token
    from sqlalchemy import text

    with get_admin_session() as session:
        urow = session.execute(
            text(
                "INSERT INTO users (email, password_hash, name, status) "
                "VALUES ('viewer@v.test','x','viewer','active') RETURNING id"
            )
        ).one()
        session.execute(
            text(
                "INSERT INTO tenant_users (tenant_id, user_id, role, accepted_at) "
                "VALUES (:t, :u, 'viewer', now())"
            ),
            {"t": tid, "u": str(urow.id)},
        )
    token_v = create_access_token(user_id=str(urow.id), tenant_id=tid, role="viewer")

    resp = client.get("/files", headers=_auth(token_v))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


# ---------------------------------------------------------------------------
# GET /files/{id}/url — presigned + audit + cross-tenant 404
# ---------------------------------------------------------------------------


def test_url_gera_presigned_com_expires_in_3600(client) -> None:
    tid, _, token = _seed_tenant(slug="acmeu", email="o@u.test")
    file_id = _seed_file(tenant_id=tid, kind="export")

    resp = client.get(f"/files/{file_id}/url", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["expires_in"] == 3600
    assert body["url"].startswith("https://")
    assert "X-Amz-Signature=" in body["url"]
    assert "X-Amz-Expires=3600" in body["url"]
    assert body["expires_at"]


def test_url_cross_tenant_404(client) -> None:
    tid_a, _, token_a = _seed_tenant(slug="acmex1", email="a@x.test")
    _tid_b, _, token_b = _seed_tenant(slug="acmex2", email="b@x.test")
    file_id = _seed_file(tenant_id=tid_a, kind="export")

    resp = client.get(f"/files/{file_id}/url", headers=_auth(token_b))
    assert resp.status_code == 404


def test_url_grava_audit_sem_vazar_url(client) -> None:
    tid, uid, token = _seed_tenant(slug="acmea", email="o@a.test")
    file_id = _seed_file(tenant_id=tid, kind="report")

    resp = client.get(f"/files/{file_id}/url", headers=_auth(token))
    assert resp.status_code == 200
    url = resp.json()["url"]

    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        rows = session.execute(
            text(
                "SELECT action, resource_type, resource_id, "
                "       actor_user_id, metadata::text AS m "
                "  FROM audit_logs WHERE tenant_id = :t "
                "ORDER BY created_at"
            ),
            {"t": tid},
        ).all()

    assert len(rows) == 1
    row = rows[0]
    assert row.action == "file.download_url"
    assert row.resource_type == "file"
    assert row.resource_id == file_id
    assert str(row.actor_user_id) == uid
    meta = json.loads(row.m)
    assert meta["file_id"] == file_id
    assert meta["kind"] == "report"
    assert meta["expires_in"] == 3600
    assert "object_key" in meta
    # Garantia do DoD: a URL assinada (com Signature/Credential) nao
    # pode estar em lugar nenhum do audit_log.
    assert "X-Amz-Signature" not in row.m
    assert url not in row.m


def test_url_404_quando_file_nao_existe(client) -> None:
    _, _, token = _seed_tenant(slug="acme404", email="o@404.test")
    resp = client.get(
        f"/files/{uuid.uuid4()}/url", headers=_auth(token)
    )
    assert resp.status_code == 404


def test_url_viewer_pode_gerar(client) -> None:
    tid, _, _ = _seed_tenant(slug="acmevu", email="o@vu.test")
    file_id = _seed_file(tenant_id=tid, kind="export")

    from api.db import get_admin_session
    from api.security.jwt import create_access_token
    from sqlalchemy import text

    with get_admin_session() as session:
        urow = session.execute(
            text(
                "INSERT INTO users (email, password_hash, name, status) "
                "VALUES ('vu@vu.test','x','vu','active') RETURNING id"
            )
        ).one()
        session.execute(
            text(
                "INSERT INTO tenant_users (tenant_id, user_id, role, accepted_at) "
                "VALUES (:t, :u, 'viewer', now())"
            ),
            {"t": tid, "u": str(urow.id)},
        )
    token_v = create_access_token(user_id=str(urow.id), tenant_id=tid, role="viewer")

    resp = client.get(f"/files/{file_id}/url", headers=_auth(token_v))
    assert resp.status_code == 200
    assert resp.json()["expires_in"] == 3600
