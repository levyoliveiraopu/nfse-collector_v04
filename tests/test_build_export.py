"""Testes do `worker_core.jobs.build_export` (API-15).

Gated por:
- `TEST_DATABASE_URL` (Postgres real com migrations ate 0017).
- `moto` para mockar S3.

Cobertura:
- Caminho feliz: 3 XMLs viram 1 ZIP, `exports.status='ready'`,
  `files` ganha linha com `expires_at ≈ now+30d` e `notifications`
  ganha 2 linhas (inapp + email) tipo `export.ready`.
- Limite 2 GB: `EXPORT_MAX_BYTES=100` + 1 XML de 500 bytes levanta
  `ExportError('size_limit_exceeded')` e marca `exports.status='failed'`.
- Empty: periodo sem itens -> `status='empty'`, sem `files` novos.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL nao definida — pulando integracao Postgres.",
)

moto = pytest.importorskip("moto")
psycopg = pytest.importorskip("psycopg")

from moto import mock_aws  # noqa: E402


BUCKET = "nfse-test-export-worker"


def _dsn() -> str:
    raw = os.environ["TEST_DATABASE_URL"]
    return raw.replace("postgresql+psycopg://", "postgresql://")


@pytest.fixture
def s3_env(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", BUCKET)
    monkeypatch.setenv("S3_REGION", "us-east-1")
    monkeypatch.delenv("S3_ENDPOINT", raising=False)
    monkeypatch.setenv("S3_KEY_ID", "testing")
    monkeypatch.setenv("S3_APPLICATION_KEY", "testing")
    monkeypatch.setenv("S3_FORCE_PATH_STYLE", "true")
    monkeypatch.setenv("S3_EXECUTIONS_PREFIX", "tenants/")
    monkeypatch.setenv("S3_EXPORTS_PREFIX", "tenants-exports/")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def db_env(monkeypatch):
    monkeypatch.setenv("WORKER_DATABASE_URL", _dsn())


@pytest.fixture
def clean_db():
    """TRUNCATE tabelas tocadas antes e depois de cada teste."""
    tables = (
        "notifications, audit_logs, exports, execution_items, executions, "
        "files, company_credentials, companies, refresh_tokens, "
        "tenant_users, users, subscriptions, tenants, plans"
    )
    with psycopg.connect(_dsn(), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE {tables} CASCADE")
    yield
    with psycopg.connect(_dsn(), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE {tables} CASCADE")


def _seed(
    *,
    n_items: int,
    xml_bytes_each: int = 200,
    period_start=None,
    period_end=None,
) -> dict:
    """Semeia 1 tenant + 1 company + 1 execution + N itens + N XMLs no S3.

    Precisa rodar dentro do contexto `mock_aws()` para que o PUT no
    S3 seja capturado. Retorna dict com ids e object_keys.
    """
    import boto3

    tid = str(uuid.uuid4())
    uid = str(uuid.uuid4())
    cid = str(uuid.uuid4())
    eid = str(uuid.uuid4())
    export_id = str(uuid.uuid4())
    pstart = period_start or "2026-01-01"
    pend = period_end or "2026-01-31"

    object_keys: list[tuple[int, str]] = []
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BUCKET)
    xml_payload = b"<nfse>%b</nfse>" % (b"x" * max(0, xml_bytes_each - 20))

    with psycopg.connect(_dsn(), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tenants (id, name, slug) VALUES (%s, 'T', 't1')",
                (tid,),
            )
            cur.execute(
                "INSERT INTO users (id, email, password_hash, name, status) "
                "VALUES (%s, 'u@t1.test', 'x', 'U', 'active')",
                (uid,),
            )
            cur.execute(
                "INSERT INTO tenant_users (tenant_id, user_id, role, accepted_at) "
                "VALUES (%s, %s, 'owner', now())",
                (tid, uid),
            )
            cur.execute(
                "INSERT INTO companies "
                "(id, tenant_id, cnpj, razao_social, municipio_ibge, uf, status) "
                "VALUES (%s, %s, '11222333000181', 'Acme', '3550308', 'SP', 'active')",
                (cid, tid),
            )
            cur.execute(
                "INSERT INTO executions "
                "(id, tenant_id, company_id, trigger, period_start, period_end, status) "
                "VALUES (%s, %s, %s, 'manual', %s, %s, 'succeeded')",
                (eid, tid, cid, pstart, pend),
            )
            # 1 execution_item por n_items, data_emissao no meio do periodo.
            for i in range(n_items):
                nsu = 1000 + i
                object_key = f"tenants/{tid}/executions/{eid}/{nsu}.xml"
                object_keys.append((nsu, object_key))
                cur.execute(
                    "INSERT INTO execution_items "
                    "(execution_id, tenant_id, nsu, chave_nfse, "
                    " cnpj_emitente, data_emissao, xml_object_key, status) "
                    "VALUES (%s, %s, %s, %s, '11222333000181', %s, %s, 'ok')",
                    (
                        eid,
                        tid,
                        nsu,
                        f"chave-{i:04d}",
                        f"{pstart}T10:00:00Z",
                        object_key,
                    ),
                )
                s3.put_object(Bucket=BUCKET, Key=object_key, Body=xml_payload)

            # Insere o pedido de export (analogo ao que POST /exports faria).
            cur.execute(
                "INSERT INTO exports "
                "(id, tenant_id, company_id, requested_by_user_id, kind, "
                " period_start, period_end, status) "
                "VALUES (%s, %s, %s, %s, 'zip_xml', %s, %s, 'queued')",
                (export_id, tid, cid, uid, pstart, pend),
            )

    return {
        "tenant_id": tid,
        "user_id": uid,
        "company_id": cid,
        "execution_id": eid,
        "export_id": export_id,
        "object_keys": object_keys,
    }


def test_build_export_happy_path(db_env, s3_env, clean_db) -> None:
    from worker_core.jobs import build_export

    with mock_aws():
        seed = _seed(n_items=3, xml_bytes_each=200)
        result = build_export(seed["export_id"])

    assert result["status"] == "ready"
    assert result["items"] == 3
    assert result["bytes"] > 0
    assert result["object_key"].startswith(f"tenants-exports/{seed['tenant_id']}/")
    assert result["object_key"].endswith(".zip")

    with psycopg.connect(_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, file_id, items_count, total_bytes, "
                "started_at, finished_at FROM exports WHERE id = %s",
                (seed["export_id"],),
            )
            export_row = cur.fetchone()
            assert export_row[0] == "ready"
            assert export_row[1] is not None  # file_id
            assert export_row[2] == 3
            assert export_row[3] > 0
            assert export_row[4] is not None
            assert export_row[5] is not None

            # files ganhou 1 linha kind=export com expires_at ~ now+30d.
            cur.execute(
                "SELECT id, kind, object_key, bytes, expires_at "
                "FROM files WHERE tenant_id = %s AND kind = 'export'",
                (seed["tenant_id"],),
            )
            file_rows = cur.fetchall()
            assert len(file_rows) == 1
            fid = file_rows[0][0]
            assert file_rows[0][1] == "export"
            assert file_rows[0][3] > 0
            expires_at = file_rows[0][4]
            now = datetime.now(tz=timezone.utc)
            delta = expires_at - now
            # Janela generosa de 29..31 dias para tolerar jitter.
            assert timedelta(days=29) < delta < timedelta(days=31)

            # `exports.file_id` aponta para a linha criada em `files`.
            assert str(export_row[1]) == str(fid)

            # notifications: 2 linhas (inapp + email).
            cur.execute(
                "SELECT channel, type, status, payload "
                "FROM notifications WHERE tenant_id = %s ORDER BY channel",
                (seed["tenant_id"],),
            )
            notifs = cur.fetchall()
            assert len(notifs) == 2
            channels = {row[0] for row in notifs}
            assert channels == {"email", "inapp"}
            for row in notifs:
                assert row[1] == "export.ready"
                assert row[2] == "pending"
                assert row[3]["export_id"] == seed["export_id"]
                assert row[3]["file_id"] == str(fid)
                assert row[3]["kind"] == "zip_xml"


def test_build_export_limite_2gb_marca_failed(
    db_env, s3_env, clean_db, monkeypatch
) -> None:
    """EXPORT_MAX_BYTES muito baixo -> size_limit_exceeded."""
    from worker_core.jobs import ExportError, build_export

    monkeypatch.setenv("EXPORT_MAX_BYTES", "100")

    with mock_aws():
        seed = _seed(n_items=1, xml_bytes_each=500)
        with pytest.raises(ExportError) as exc:
            build_export(seed["export_id"])
        assert exc.value.code == "size_limit_exceeded"

    with psycopg.connect(_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, error_code FROM exports WHERE id = %s",
                (seed["export_id"],),
            )
            row = cur.fetchone()
            assert row[0] == "failed"
            assert row[1] == "size_limit_exceeded"
            # Nao criamos file.
            cur.execute(
                "SELECT COUNT(*) FROM files WHERE tenant_id = %s AND kind = 'export'",
                (seed["tenant_id"],),
            )
            assert cur.fetchone()[0] == 0
            # Nao enviamos notificacoes.
            cur.execute(
                "SELECT COUNT(*) FROM notifications WHERE tenant_id = %s",
                (seed["tenant_id"],),
            )
            assert cur.fetchone()[0] == 0


def test_build_export_periodo_vazio_marca_empty(db_env, s3_env, clean_db) -> None:
    """Sem items no periodo -> exports.status='empty'."""
    from worker_core.jobs import build_export

    with mock_aws():
        # Semeia 0 itens (nenhum execution_item). A company existe.
        seed = _seed(n_items=0)
        result = build_export(seed["export_id"])

    assert result == {"status": "empty", "items": 0}

    with psycopg.connect(_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM exports WHERE id = %s", (seed["export_id"],)
            )
            assert cur.fetchone()[0] == "empty"
            cur.execute(
                "SELECT COUNT(*) FROM files WHERE tenant_id = %s AND kind = 'export'",
                (seed["tenant_id"],),
            )
            assert cur.fetchone()[0] == 0
