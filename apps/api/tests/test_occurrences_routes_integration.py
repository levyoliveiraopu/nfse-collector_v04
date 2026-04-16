"""Testes de integracao do CRUD de `/occurrences` (API-09).

Mesmo padrao de `test_companies_routes_integration.py`: gated por
`TEST_DATABASE_URL` (Postgres real com todas as migrations aplicadas
0001..0015), TRUNCATE antes de cada teste e seed inline.

Cobertura:
- GET lista com filtros (status, severity, company_id) e paginacao.
- GET detalhe + 404 cross-tenant via RLS.
- viewer -> 403 em ack/resolve/assign.
- acknowledge feliz; idempotencia em ja-`ack`; 409 em estado terminal.
- resolve sem nota -> 422; com nota grava `resolved_at`.
- assign valida membership do tenant; user de outro tenant -> 404.
- audit_logs ganha 1 linha por mutacao com `action` correto.
"""

from __future__ import annotations

import os
from typing import Optional
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL nao definida — pulando integracao Postgres.",
)


VALID_CNPJ_A = "11222333000181"
VALID_CNPJ_B = "04252011000110"


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
                "TRUNCATE occurrences, audit_logs, companies, refresh_tokens, "
                "tenant_users, users, subscriptions, tenants, plans CASCADE"
            )
        )

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def _seed_tenant(
    *,
    slug: str,
    email: str,
    role: str = "owner",
) -> tuple[str, str, str]:
    """Cria tenant + user + tenant_users; devolve (tenant_id, user_id, token)."""
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


def _add_user_to_tenant(*, tenant_id: str, email: str, role: str) -> tuple[str, str]:
    """Cria user adicional no tenant; devolve (user_id, token)."""
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
    token = create_access_token(user_id=uid, tenant_id=tenant_id, role=role)
    return uid, token


def _seed_company(*, tenant_id: str, cnpj: str = VALID_CNPJ_A) -> str:
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        row = session.execute(
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
        return str(row.id)


def _seed_occurrence(
    *,
    tenant_id: str,
    company_id: str,
    code: str = "CERT_EXPIRING",
    severity: str = "warning",
    title: str = "Certificado vence em 30 dias",
    status_: str = "open",
) -> str:
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        row = session.execute(
            text(
                """
                INSERT INTO occurrences (
                    tenant_id, company_id, severity, code, title, status
                ) VALUES (:tid, :cid, :sev, :code, :title, :st)
                RETURNING id
                """
            ),
            {
                "tid": tenant_id,
                "cid": company_id,
                "sev": severity,
                "code": code,
                "title": title,
                "st": status_,
            },
        ).one()
        return str(row.id)


def _audit_count(action: Optional[str] = None) -> int:
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        if action is None:
            row = session.execute(
                text("SELECT COUNT(*) AS n FROM audit_logs")
            ).one()
        else:
            row = session.execute(
                text("SELECT COUNT(*) AS n FROM audit_logs WHERE action = :a"),
                {"a": action},
            ).one()
    return int(row.n)


def _audit_metadata(action: str) -> dict:
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        row = session.execute(
            text(
                "SELECT metadata FROM audit_logs "
                "WHERE action = :a ORDER BY id DESC LIMIT 1"
            ),
            {"a": action},
        ).one()
    return dict(row.metadata)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------


def test_lista_e_filtros(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="o@acme.test")
    cid_a = _seed_company(tenant_id=tid, cnpj=VALID_CNPJ_A)
    cid_b = _seed_company(tenant_id=tid, cnpj=VALID_CNPJ_B)
    _seed_occurrence(tenant_id=tid, company_id=cid_a, code="CERT_EXPIRED",
                     severity="error", status_="open")
    _seed_occurrence(tenant_id=tid, company_id=cid_a, code="PORTAL_5XX",
                     severity="error", status_="ack")
    _seed_occurrence(tenant_id=tid, company_id=cid_b, code="CERT_EXPIRING",
                     severity="warning", status_="open")

    # Sem filtro: 3.
    body = client.get("/occurrences", headers=_auth(token)).json()
    assert body["total"] == 3

    # Por status.
    body = client.get("/occurrences?status=open", headers=_auth(token)).json()
    assert body["total"] == 2

    # Por severity.
    body = client.get("/occurrences?severity=error", headers=_auth(token)).json()
    assert body["total"] == 2

    # Por company.
    body = client.get(
        f"/occurrences?company_id={cid_b}", headers=_auth(token)
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "CERT_EXPIRING"

    # Combinado.
    body = client.get(
        f"/occurrences?status=open&severity=error&company_id={cid_a}",
        headers=_auth(token),
    ).json()
    assert body["total"] == 1


def test_paginacao(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="o@acme.test")
    cid = _seed_company(tenant_id=tid)
    for _ in range(3):
        _seed_occurrence(tenant_id=tid, company_id=cid, code="PORTAL_TIMEOUT")

    body = client.get("/occurrences?page=1&page_size=2", headers=_auth(token)).json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    body2 = client.get("/occurrences?page=2&page_size=2", headers=_auth(token)).json()
    assert len(body2["items"]) == 1


def test_detalhe(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="o@acme.test")
    cid = _seed_company(tenant_id=tid)
    oid = _seed_occurrence(tenant_id=tid, company_id=cid)

    resp = client.get(f"/occurrences/{oid}", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == oid
    assert body["status"] == "open"


def test_detalhe_404_quando_inexistente(client) -> None:
    _, _, token = _seed_tenant(slug="acme", email="o@acme.test")
    resp = client.get(f"/occurrences/{uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


def test_cross_tenant_isolado(client) -> None:
    tid_a, _, token_a = _seed_tenant(slug="acme", email="a@acme.test")
    tid_b, _, token_b = _seed_tenant(slug="beta", email="b@beta.test")
    cid_a = _seed_company(tenant_id=tid_a)
    oid_a = _seed_occurrence(tenant_id=tid_a, company_id=cid_a)

    # Tenant B nao enxerga.
    assert client.get(f"/occurrences/{oid_a}", headers=_auth(token_b)).status_code == 404
    body = client.get("/occurrences", headers=_auth(token_b)).json()
    assert body["total"] == 0

    # Tenant B nao consegue acknowledge/resolve/assign.
    assert (
        client.post(
            f"/occurrences/{oid_a}/acknowledge", headers=_auth(token_b)
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/occurrences/{oid_a}/resolve",
            json={"note": "tentativa hostil"},
            headers=_auth(token_b),
        ).status_code
        == 404
    )

    # Tenant A continua enxergando.
    assert client.get(f"/occurrences/{oid_a}", headers=_auth(token_a)).status_code == 200


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


def test_viewer_le_mas_nao_muda(client) -> None:
    tid, _, owner_token = _seed_tenant(slug="acme", email="o@acme.test")
    _, viewer_token = _add_user_to_tenant(
        tenant_id=tid, email="v@acme.test", role="viewer"
    )
    cid = _seed_company(tenant_id=tid)
    oid = _seed_occurrence(tenant_id=tid, company_id=cid)

    # Le ok.
    assert client.get("/occurrences", headers=_auth(viewer_token)).status_code == 200
    assert (
        client.get(f"/occurrences/{oid}", headers=_auth(viewer_token)).status_code == 200
    )

    # Nao muda.
    assert (
        client.post(
            f"/occurrences/{oid}/acknowledge", headers=_auth(viewer_token)
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/occurrences/{oid}/resolve",
            json={"note": "x"},
            headers=_auth(viewer_token),
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/occurrences/{oid}/assign",
            json={"assignee_user_id": str(uuid4())},
            headers=_auth(viewer_token),
        ).status_code
        == 403
    )

    # Owner ainda pode (sanity check).
    assert (
        client.post(
            f"/occurrences/{oid}/acknowledge", headers=_auth(owner_token)
        ).status_code
        == 200
    )


def test_operator_pode_mudar(client) -> None:
    tid, _, _ = _seed_tenant(slug="acme", email="o@acme.test")
    _, op_token = _add_user_to_tenant(
        tenant_id=tid, email="op@acme.test", role="operator"
    )
    cid = _seed_company(tenant_id=tid)
    oid = _seed_occurrence(tenant_id=tid, company_id=cid)

    assert (
        client.post(f"/occurrences/{oid}/acknowledge", headers=_auth(op_token)).status_code
        == 200
    )


# ---------------------------------------------------------------------------
# Acknowledge
# ---------------------------------------------------------------------------


def test_acknowledge_open_para_ack_com_audit(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="o@acme.test")
    cid = _seed_company(tenant_id=tid)
    oid = _seed_occurrence(tenant_id=tid, company_id=cid)

    before = _audit_count()
    resp = client.post(f"/occurrences/{oid}/acknowledge", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ack"

    assert _audit_count() == before + 1
    assert _audit_count(action="occurrence.acknowledge") == 1
    meta = _audit_metadata("occurrence.acknowledge")
    assert meta["status_from"] == "open"
    assert meta["status_to"] == "ack"


def test_acknowledge_idempotente_em_ja_ack(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="o@acme.test")
    cid = _seed_company(tenant_id=tid)
    oid = _seed_occurrence(tenant_id=tid, company_id=cid, status_="ack")

    before = _audit_count()
    resp = client.post(f"/occurrences/{oid}/acknowledge", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ack"
    # Idempotente nao audita.
    assert _audit_count() == before


def test_acknowledge_409_em_resolved(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="o@acme.test")
    cid = _seed_company(tenant_id=tid)
    oid = _seed_occurrence(tenant_id=tid, company_id=cid, status_="resolved")

    resp = client.post(f"/occurrences/{oid}/acknowledge", headers=_auth(token))
    assert resp.status_code == 409


def test_acknowledge_409_em_ignored(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="o@acme.test")
    cid = _seed_company(tenant_id=tid)
    oid = _seed_occurrence(tenant_id=tid, company_id=cid, status_="ignored")

    resp = client.post(f"/occurrences/{oid}/acknowledge", headers=_auth(token))
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------


def test_resolve_grava_resolved_at_e_audit_com_nota(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="o@acme.test")
    cid = _seed_company(tenant_id=tid)
    oid = _seed_occurrence(tenant_id=tid, company_id=cid)

    resp = client.post(
        f"/occurrences/{oid}/resolve",
        json={"note": "Cliente atualizou a credencial."},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["resolved_at"] is not None

    assert _audit_count(action="occurrence.resolve") == 1
    meta = _audit_metadata("occurrence.resolve")
    assert meta["status_from"] == "open"
    assert meta["status_to"] == "resolved"
    assert meta["note"] == "Cliente atualizou a credencial."


def test_resolve_de_ack_tambem_funciona(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="o@acme.test")
    cid = _seed_company(tenant_id=tid)
    oid = _seed_occurrence(tenant_id=tid, company_id=cid, status_="ack")

    resp = client.post(
        f"/occurrences/{oid}/resolve",
        json={"note": "ok"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"


def test_resolve_sem_nota_422(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="o@acme.test")
    cid = _seed_company(tenant_id=tid)
    oid = _seed_occurrence(tenant_id=tid, company_id=cid)

    resp = client.post(
        f"/occurrences/{oid}/resolve",
        json={},
        headers=_auth(token),
    )
    assert resp.status_code == 422


def test_resolve_com_nota_vazia_422(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="o@acme.test")
    cid = _seed_company(tenant_id=tid)
    oid = _seed_occurrence(tenant_id=tid, company_id=cid)

    resp = client.post(
        f"/occurrences/{oid}/resolve",
        json={"note": ""},
        headers=_auth(token),
    )
    assert resp.status_code == 422


def test_resolve_409_em_ignored(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="o@acme.test")
    cid = _seed_company(tenant_id=tid)
    oid = _seed_occurrence(tenant_id=tid, company_id=cid, status_="ignored")

    resp = client.post(
        f"/occurrences/{oid}/resolve",
        json={"note": "tentativa"},
        headers=_auth(token),
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Assign
# ---------------------------------------------------------------------------


def test_assign_valido_grava_assignee_e_audit(client) -> None:
    tid, owner_uid, token = _seed_tenant(slug="acme", email="o@acme.test")
    other_uid, _ = _add_user_to_tenant(
        tenant_id=tid, email="op@acme.test", role="operator"
    )
    cid = _seed_company(tenant_id=tid)
    oid = _seed_occurrence(tenant_id=tid, company_id=cid)

    resp = client.post(
        f"/occurrences/{oid}/assign",
        json={"assignee_user_id": other_uid},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["assignee_user_id"] == other_uid

    assert _audit_count(action="occurrence.assign") == 1
    meta = _audit_metadata("occurrence.assign")
    assert meta["assignee_user_id"] == other_uid
    assert meta["previous_assignee_user_id"] is None


def test_assign_user_de_outro_tenant_404(client) -> None:
    tid_a, _, token_a = _seed_tenant(slug="acme", email="a@acme.test")
    tid_b, foreign_uid, _ = _seed_tenant(slug="beta", email="b@beta.test")
    cid_a = _seed_company(tenant_id=tid_a)
    oid = _seed_occurrence(tenant_id=tid_a, company_id=cid_a)

    resp = client.post(
        f"/occurrences/{oid}/assign",
        json={"assignee_user_id": foreign_uid},
        headers=_auth(token_a),
    )
    assert resp.status_code == 404
    assert "membro" in resp.json()["detail"]


def test_assign_user_inexistente_404(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="o@acme.test")
    cid = _seed_company(tenant_id=tid)
    oid = _seed_occurrence(tenant_id=tid, company_id=cid)

    resp = client.post(
        f"/occurrences/{oid}/assign",
        json={"assignee_user_id": str(uuid4())},
        headers=_auth(token),
    )
    assert resp.status_code == 404


def test_reassign_registra_previous(client) -> None:
    tid, _, token = _seed_tenant(slug="acme", email="o@acme.test")
    uid_1, _ = _add_user_to_tenant(tenant_id=tid, email="op1@acme.test", role="operator")
    uid_2, _ = _add_user_to_tenant(tenant_id=tid, email="op2@acme.test", role="operator")
    cid = _seed_company(tenant_id=tid)
    oid = _seed_occurrence(tenant_id=tid, company_id=cid)

    # Primeira atribuicao.
    client.post(
        f"/occurrences/{oid}/assign",
        json={"assignee_user_id": uid_1},
        headers=_auth(token),
    )
    # Re-atribuicao.
    resp = client.post(
        f"/occurrences/{oid}/assign",
        json={"assignee_user_id": uid_2},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["assignee_user_id"] == uid_2

    meta = _audit_metadata("occurrence.assign")
    assert meta["assignee_user_id"] == uid_2
    assert meta["previous_assignee_user_id"] == uid_1


# ---------------------------------------------------------------------------
# OpenAPI / 401
# ---------------------------------------------------------------------------


def test_token_ausente_401(client) -> None:
    resp = client.get("/occurrences")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_openapi_lista_endpoints(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/occurrences" in paths
    assert "/occurrences/{occurrence_id}" in paths
    assert "/occurrences/{occurrence_id}/acknowledge" in paths
    assert "/occurrences/{occurrence_id}/resolve" in paths
    assert "/occurrences/{occurrence_id}/assign" in paths
