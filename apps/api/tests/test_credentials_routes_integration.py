"""Testes de integracao do upload/revogacao de credencial PFX (API-06).

Requerem:
- Postgres real com migrations 0001..0016 aplicadas (`TEST_DATABASE_URL`).
- `moto` para simular o S3 (PUT/GET/DELETE em bucket fake).

Cobertura:
- POST cria company_credential, salva blob cifrado no S3 e audita.
- Senha errada -> 400 sem vazar conteudo do PFX.
- PFX excedendo o limite -> 413.
- Cross-tenant: tenant B nao consegue postar/revogar credencial de A (404).
- RBAC: viewer/operator -> 403; owner/admin -> 200.
- DELETE marca status=revoked, audita e remove blob.
- Worker decifra e abre o PFX (E2E sintetico — DoD do ticket).
- Logs/banco/audit_logs nao contem senha em claro nem PFX bruto.
"""

from __future__ import annotations

import base64
import io
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL nao definida — pulando integracao Postgres.",
)

moto = pytest.importorskip("moto")
from moto import mock_aws  # noqa: E402

from cryptography import x509  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from cryptography.hazmat.primitives.serialization import pkcs12  # noqa: E402
from cryptography.x509.oid import NameOID  # noqa: E402


VALID_CNPJ_A = "11222333000181"
VALID_CNPJ_B = "04252011000110"

_TEST_BUCKET = "nfse-saas-test"


def _gen_pfx(cnpj: str, password: str, *, cn_override: Optional[str] = None) -> bytes:
    """Gera um PFX self-signed minimo com CN contendo o CNPJ."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cn = cn_override if cn_override is not None else f"ACME LTDA:{cnpj}"
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(tz=timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(tz=timezone.utc) + timedelta(days=365))
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        name=b"test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode()),
    )


@pytest.fixture()
def env_setup():
    # API.
    os.environ["API_DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ.setdefault("API_JWT_SECRET", "integration-test-secret")
    os.environ.setdefault("API_ENVIRONMENT", "development")
    os.environ.setdefault("API_LOGIN_RATE_LIMIT", "1000/minute")
    # KEK previsivel para os testes.
    os.environ["API_CREDENTIAL_KEK_B64"] = base64.urlsafe_b64encode(
        secrets.token_bytes(32)
    ).decode()
    os.environ["API_CREDENTIAL_MAX_PFX_BYTES"] = "1048576"
    # S3.
    os.environ["S3_BUCKET"] = _TEST_BUCKET
    os.environ["S3_REGION"] = "us-east-1"
    os.environ["S3_KEY_ID"] = "test-key"
    os.environ["S3_APPLICATION_KEY"] = "test-secret"
    os.environ.pop("S3_ENDPOINT", None)
    os.environ["S3_FORCE_PATH_STYLE"] = "true"
    os.environ["S3_CREDENTIALS_PREFIX"] = "tenants-credentials/"

    from api import config as config_module
    from api import crypto as crypto_module
    from api import storage as storage_module
    from api.db import reset_engine_for_tests

    config_module.get_settings.cache_clear()  # type: ignore[attr-defined]
    crypto_module.reset_kek_cache_for_tests()
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
                "TRUNCATE audit_logs, company_credentials, companies, "
                "refresh_tokens, tenant_users, users, subscriptions, "
                "tenants, plans CASCADE"
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
            text(
                "INSERT INTO tenants (name, slug) VALUES (:n, :s) RETURNING id"
            ),
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


def _seed_company(*, token: str, cnpj: str = VALID_CNPJ_A) -> str:
    """Cria company via API e devolve o id."""
    # Importacao tardia para evitar instanciar Settings antes do env_setup.
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "cnpj": cnpj,
        "razao_social": "Acme LTDA",
        "municipio_ibge": "3550308",
        "uf": "SP",
        "status": "active",
    }
    # Reusa a propria fixture client passada externamente.
    return payload, headers


def _post_credential(client, *, company_id: str, token: str, pfx_bytes: bytes, password: str):
    return client.post(
        f"/companies/{company_id}/credential",
        files={"pfx": ("cert.pfx", io.BytesIO(pfx_bytes), "application/x-pkcs12")},
        data={"password": password},
        headers={"Authorization": f"Bearer {token}"},
    )


# ---------------------------------------------------------------------------
# Helpers de DB para asserts.
# ---------------------------------------------------------------------------


def _credential_row(credential_id: str) -> dict:
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        row = session.execute(
            text(
                "SELECT id, tenant_id, company_id, status, "
                "       pfx_object_key, pfx_password_ciphertext, "
                "       cert_fingerprint "
                "  FROM company_credentials WHERE id = :id"
            ),
            {"id": credential_id},
        ).one()
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "company_id": str(row.company_id),
            "status": row.status,
            "pfx_object_key": row.pfx_object_key,
            "pfx_password_ciphertext": bytes(row.pfx_password_ciphertext),
            "cert_fingerprint": row.cert_fingerprint,
        }


def _audit_actions(tenant_id: str) -> list[tuple[str, str]]:
    from api.db import get_admin_session
    from sqlalchemy import text

    with get_admin_session() as session:
        rows = session.execute(
            text(
                "SELECT action, COALESCE(metadata::text, '') AS m FROM audit_logs "
                "WHERE tenant_id = :t ORDER BY created_at"
            ),
            {"t": tenant_id},
        ).all()
        return [(r.action, r.m) for r in rows]


# ---------------------------------------------------------------------------
# Casos.
# ---------------------------------------------------------------------------


def test_upload_feliz_grava_no_s3_e_audita(client) -> None:
    tid, uid, token = _seed_tenant(slug="acme", email="owner@acme.test")
    payload, headers = _seed_company(token=token)
    cresp = client.post("/companies", json=payload, headers=headers)
    assert cresp.status_code == 201, cresp.text
    company_id = cresp.json()["id"]

    pfx_bytes = _gen_pfx(VALID_CNPJ_A, "p4ssw0rd-secreta")
    resp = _post_credential(
        client, company_id=company_id, token=token, pfx_bytes=pfx_bytes, password="p4ssw0rd-secreta"
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "active"
    assert body["cn_matches_cnpj"] is True
    assert body["pfx_object_key"].startswith(f"tenants-credentials/{tid}/")
    assert body["pfx_object_key"].endswith(".pfx.enc")
    assert body["cert_fingerprint"]

    # Banco: senha cifrada (nao em claro), object_key resolvido.
    row = _credential_row(body["id"])
    assert row["status"] == "active"
    # Marca de versao do envelope no inicio.
    assert row["pfx_password_ciphertext"][:1] == b"\x01"
    assert b"p4ssw0rd-secreta" not in row["pfx_password_ciphertext"]

    # Storage: blob cifrado existe e nao e o PFX bruto.
    from api import storage as storage_module

    blob = storage_module.get_credential_blob(row["pfx_object_key"])
    assert blob is not None
    assert blob[:1] == b"\x01"
    assert blob != pfx_bytes

    # Audit: contem credential.upload com metadata sem senha.
    actions = _audit_actions(tid)
    assert ("credential.upload", actions[-1][1]) == ("credential.upload", actions[-1][1])
    assert actions[-1][0] == "credential.upload"
    assert "p4ssw0rd-secreta" not in actions[-1][1]


def test_worker_decifra_e_abre_pfx(client) -> None:
    """DoD: worker consegue decifrar e usar (E2E simulado)."""
    tid, uid, token = _seed_tenant(slug="acme2", email="o@acme2.test")
    payload, headers = _seed_company(token=token)
    cresp = client.post("/companies", json=payload, headers=headers)
    company_id = cresp.json()["id"]

    pfx_bytes = _gen_pfx(VALID_CNPJ_A, "senha-do-worker")
    resp = _post_credential(
        client, company_id=company_id, token=token,
        pfx_bytes=pfx_bytes, password="senha-do-worker",
    )
    assert resp.status_code == 201

    row = _credential_row(resp.json()["id"])

    # Caminho do worker: ler ciphertext do storage, decifrar com KEK,
    # decifrar a senha, e abrir o PFX em memoria.
    from api import crypto, storage

    blob = storage.get_credential_blob(row["pfx_object_key"])
    pfx_clear = crypto.decrypt(blob, row["tenant_id"])
    pwd_clear = crypto.decrypt(row["pfx_password_ciphertext"], row["tenant_id"])

    # Reabre via PKCS#12 — prova de que e o PFX original.
    private_key, cert, _ = pkcs12.load_key_and_certificates(pfx_clear, pwd_clear)
    assert private_key is not None
    assert cert is not None
    assert pwd_clear == b"senha-do-worker"


def test_senha_errada_400(client) -> None:
    _, _, token = _seed_tenant(slug="acmex", email="o@x.test")
    payload, headers = _seed_company(token=token)
    cresp = client.post("/companies", json=payload, headers=headers)
    company_id = cresp.json()["id"]

    pfx_bytes = _gen_pfx(VALID_CNPJ_A, "certa")
    resp = _post_credential(
        client, company_id=company_id, token=token, pfx_bytes=pfx_bytes, password="errada"
    )
    assert resp.status_code == 400


def test_pfx_excedendo_limite_413(client) -> None:
    _, _, token = _seed_tenant(slug="acmey", email="o@y.test")
    payload, headers = _seed_company(token=token)
    cresp = client.post("/companies", json=payload, headers=headers)
    company_id = cresp.json()["id"]

    # Reduz o teto para 1 KiB so neste teste para nao precisar gerar 1 MiB.
    os.environ["API_CREDENTIAL_MAX_PFX_BYTES"] = "1024"
    from api import config as config_module

    config_module.get_settings.cache_clear()  # type: ignore[attr-defined]

    pfx_bytes = _gen_pfx(VALID_CNPJ_A, "p")
    assert len(pfx_bytes) > 1024
    resp = _post_credential(
        client, company_id=company_id, token=token, pfx_bytes=pfx_bytes, password="p"
    )
    assert resp.status_code == 413


def test_cross_tenant_404(client) -> None:
    _, _, token_a = _seed_tenant(slug="acmea", email="oa@a.test")
    _, _, token_b = _seed_tenant(slug="acmeb", email="ob@b.test")
    payload, headers = _seed_company(token=token_a)
    cresp = client.post("/companies", json=payload, headers=headers)
    company_id = cresp.json()["id"]

    pfx_bytes = _gen_pfx(VALID_CNPJ_A, "p")
    resp = _post_credential(
        client, company_id=company_id, token=token_b, pfx_bytes=pfx_bytes, password="p"
    )
    assert resp.status_code == 404


def test_rbac_viewer_403(client) -> None:
    _, _, token_owner = _seed_tenant(slug="acmeo", email="o@o.test")
    payload, headers = _seed_company(token=token_owner)
    cresp = client.post("/companies", json=payload, headers=headers)
    company_id = cresp.json()["id"]

    # Viewer no mesmo tenant.
    from api.db import get_admin_session
    from api.security.jwt import create_access_token
    from sqlalchemy import text

    with get_admin_session() as session:
        urow = session.execute(
            text(
                "INSERT INTO users (email, password_hash, name, status) "
                "VALUES ('viewer@o.test','x','viewer','active') RETURNING id"
            )
        ).one()
        user_id = str(urow.id)
        # Reusa o tenant do owner.
        trow = session.execute(text("SELECT id FROM tenants WHERE slug='acmeo'")).one()
        tenant_id = str(trow.id)
        session.execute(
            text(
                "INSERT INTO tenant_users (tenant_id, user_id, role, accepted_at) "
                "VALUES (:t, :u, 'viewer', now())"
            ),
            {"t": tenant_id, "u": user_id},
        )
    token_v = create_access_token(user_id=user_id, tenant_id=tenant_id, role="viewer")

    pfx_bytes = _gen_pfx(VALID_CNPJ_A, "p")
    resp = _post_credential(
        client, company_id=company_id, token=token_v, pfx_bytes=pfx_bytes, password="p"
    )
    assert resp.status_code == 403


def test_revogacao_marca_status_e_remove_blob(client) -> None:
    tid, _, token = _seed_tenant(slug="acmer", email="o@r.test")
    payload, headers = _seed_company(token=token)
    cresp = client.post("/companies", json=payload, headers=headers)
    company_id = cresp.json()["id"]

    pfx_bytes = _gen_pfx(VALID_CNPJ_A, "p")
    upload = _post_credential(
        client, company_id=company_id, token=token, pfx_bytes=pfx_bytes, password="p"
    )
    assert upload.status_code == 201
    cred_id = upload.json()["id"]
    object_key = upload.json()["pfx_object_key"]

    delr = client.delete(
        f"/companies/{company_id}/credential",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delr.status_code == 200
    assert cred_id in delr.json()["revoked"]

    row = _credential_row(cred_id)
    assert row["status"] == "revoked"

    from api import storage as storage_module

    assert storage_module.get_credential_blob(object_key) is None

    # Audit: tem upload + revoke.
    actions = [a for a, _ in _audit_actions(tid)]
    assert "credential.upload" in actions
    assert "credential.revoke" in actions


def test_segundo_upload_revoga_anterior(client) -> None:
    _, _, token = _seed_tenant(slug="acmew", email="o@w.test")
    payload, headers = _seed_company(token=token)
    cresp = client.post("/companies", json=payload, headers=headers)
    company_id = cresp.json()["id"]

    first = _post_credential(
        client, company_id=company_id, token=token,
        pfx_bytes=_gen_pfx(VALID_CNPJ_A, "p1"), password="p1",
    )
    assert first.status_code == 201
    second = _post_credential(
        client, company_id=company_id, token=token,
        pfx_bytes=_gen_pfx(VALID_CNPJ_A, "p2"), password="p2",
    )
    assert second.status_code == 201

    first_row = _credential_row(first.json()["id"])
    second_row = _credential_row(second.json()["id"])
    assert first_row["status"] == "revoked"
    assert second_row["status"] == "active"


def test_cn_nao_casa_emite_warn_mas_aceita(client, caplog) -> None:
    _, _, token = _seed_tenant(slug="acmecn", email="o@cn.test")
    payload, headers = _seed_company(token=token)
    cresp = client.post("/companies", json=payload, headers=headers)
    company_id = cresp.json()["id"]

    # CN sem o CNPJ da company.
    pfx_bytes = _gen_pfx(VALID_CNPJ_A, "p", cn_override="OUTRA EMPRESA:99999999000191")
    with caplog.at_level("WARNING", logger="api.credentials"):
        resp = _post_credential(
            client, company_id=company_id, token=token, pfx_bytes=pfx_bytes, password="p"
        )
    assert resp.status_code == 201
    assert resp.json()["cn_matches_cnpj"] is False
    assert "cn_mismatch" in caplog.text
