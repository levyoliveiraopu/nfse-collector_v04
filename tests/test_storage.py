"""Testes do cliente S3 do worker-core (CORE-05)."""

from __future__ import annotations

import hashlib
import os
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import boto3
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from moto import mock_aws

from worker_core.storage import (
    S3Settings,
    S3StorageClient,
    StorageError,
    UploadResult,
    _is_transient,
    export_object_key,
    xml_object_key,
)

BUCKET = "nfse-test-bucket"
REGION = "us-east-1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def s3_env(monkeypatch):
    """Exporta vars S3_* completas apontando para o bucket de teste."""
    monkeypatch.setenv("S3_BUCKET", BUCKET)
    monkeypatch.setenv("S3_REGION", REGION)
    monkeypatch.delenv("S3_ENDPOINT", raising=False)
    monkeypatch.setenv("S3_KEY_ID", "testing")
    monkeypatch.setenv("S3_APPLICATION_KEY", "testing")
    monkeypatch.setenv("S3_FORCE_PATH_STYLE", "true")
    monkeypatch.setenv("S3_EXECUTIONS_PREFIX", "tenants/")
    monkeypatch.setenv("S3_EXPORTS_PREFIX", "tenants-exports/")
    # moto precisa de AWS_* basico na env global
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)


@pytest.fixture
def moto_bucket(s3_env):
    """Sobe S3 mockado + bucket. Devolve o client boto3 direto (para asserts)."""
    with mock_aws():
        client = boto3.client("s3", region_name=REGION)
        client.create_bucket(Bucket=BUCKET)
        yield client


# ---------------------------------------------------------------------------
# Object key builders
# ---------------------------------------------------------------------------


class TestXmlObjectKey:
    def test_formato_canonico(self):
        tid = UUID("11111111-1111-1111-1111-111111111111")
        eid = UUID("22222222-2222-2222-2222-222222222222")
        assert xml_object_key(tid, eid, 42) == (
            f"tenants/{tid}/executions/{eid}/42.xml"
        )

    def test_aceita_uuid_como_string(self):
        tid = "11111111-1111-1111-1111-111111111111"
        eid = "22222222-2222-2222-2222-222222222222"
        key = xml_object_key(tid, eid, 0)
        assert key.endswith("/0.xml")
        assert "executions/" in key

    def test_prefix_sem_slash_normaliza(self):
        key = xml_object_key(uuid4(), uuid4(), 1, prefix="tenants")
        assert key.startswith("tenants/")

    def test_prefix_customizado(self):
        key = xml_object_key(uuid4(), uuid4(), 1, prefix="alt-prefix/")
        assert key.startswith("alt-prefix/")

    def test_nsu_zero_aceito(self):
        key = xml_object_key(uuid4(), uuid4(), 0)
        assert key.endswith("/0.xml")

    def test_nsu_negativo_rejeita(self):
        with pytest.raises(ValueError, match="nsu"):
            xml_object_key(uuid4(), uuid4(), -1)

    def test_nsu_nao_int_rejeita(self):
        with pytest.raises(ValueError, match="nsu"):
            xml_object_key(uuid4(), uuid4(), "42")  # type: ignore[arg-type]

    def test_nsu_bool_rejeita(self):
        # bool e subclass de int; precisamos barrar explicitamente.
        with pytest.raises(ValueError, match="nsu"):
            xml_object_key(uuid4(), uuid4(), True)  # type: ignore[arg-type]

    def test_uuid_invalido_rejeita(self):
        with pytest.raises(ValueError, match="tenant_id"):
            xml_object_key("nao-uuid", uuid4(), 1)
        with pytest.raises(ValueError, match="execution_id"):
            xml_object_key(uuid4(), "nao-uuid", 1)


class TestExportObjectKey:
    def test_formato_canonico(self):
        tid = UUID("11111111-1111-1111-1111-111111111111")
        fid = UUID("33333333-3333-3333-3333-333333333333")
        key = export_object_key(tid, fid, "xlsx")
        assert key == f"tenants-exports/{tid}/{fid}.xlsx"

    def test_ext_com_ponto_inicial(self):
        key = export_object_key(uuid4(), uuid4(), ".xlsx")
        assert key.endswith(".xlsx")

    def test_ext_maiusculas_normaliza(self):
        key = export_object_key(uuid4(), uuid4(), "ZIP")
        assert key.endswith(".zip")

    def test_ext_vazia_rejeita(self):
        with pytest.raises(ValueError, match="ext"):
            export_object_key(uuid4(), uuid4(), "")

    def test_ext_invalida_rejeita(self):
        with pytest.raises(ValueError, match="ext"):
            export_object_key(uuid4(), uuid4(), "xl sx")
        with pytest.raises(ValueError, match="ext"):
            export_object_key(uuid4(), uuid4(), "x/s")


# ---------------------------------------------------------------------------
# S3Settings
# ---------------------------------------------------------------------------


class TestS3Settings:
    def test_bucket_obrigatorio(self, monkeypatch):
        monkeypatch.delenv("S3_BUCKET", raising=False)
        with pytest.raises(StorageError, match="S3_BUCKET"):
            S3Settings.from_env({})

    def test_defaults(self, monkeypatch):
        cfg = S3Settings.from_env({"S3_BUCKET": "b"})
        assert cfg.bucket == "b"
        assert cfg.executions_prefix == "tenants/"
        assert cfg.exports_prefix == "tenants-exports/"
        assert cfg.force_path_style is True

    def test_force_path_style_false(self):
        cfg = S3Settings.from_env(
            {"S3_BUCKET": "b", "S3_FORCE_PATH_STYLE": "false"}
        )
        assert cfg.force_path_style is False

    def test_envs_completas(self):
        cfg = S3Settings.from_env(
            {
                "S3_BUCKET": "mybucket",
                "S3_REGION": "us-west-004",
                "S3_ENDPOINT": "https://example.com",
                "S3_KEY_ID": "k",
                "S3_APPLICATION_KEY": "s",
                "S3_EXECUTIONS_PREFIX": "alt/",
                "S3_EXPORTS_PREFIX": "alt-exp/",
            }
        )
        assert cfg.region == "us-west-004"
        assert cfg.endpoint == "https://example.com"
        assert cfg.key_id == "k"
        assert cfg.application_key == "s"
        assert cfg.executions_prefix == "alt/"
        assert cfg.exports_prefix == "alt-exp/"


# ---------------------------------------------------------------------------
# Round-trip via moto
# ---------------------------------------------------------------------------


class TestUploadXml:
    def test_round_trip(self, moto_bucket):
        client = S3StorageClient()
        tid = uuid4()
        eid = uuid4()
        payload = b"<NFSe><numero>1</numero></NFSe>"

        result = client.upload_xml(tid, eid, 42, payload)

        assert isinstance(result, UploadResult)
        assert result.object_key == f"tenants/{tid}/executions/{eid}/42.xml"
        assert result.size == len(payload)
        assert result.sha256 == hashlib.sha256(payload).hexdigest()
        assert len(result.sha256) == 64

        # Bytes no bucket batem com o que subimos.
        obj = moto_bucket.get_object(Bucket=BUCKET, Key=result.object_key)
        assert obj["Body"].read() == payload
        assert obj["ContentType"] == "application/xml"
        assert obj["Metadata"]["sha256"] == result.sha256
        assert obj["Metadata"]["nsu"] == "42"

    def test_body_nao_bytes_rejeita(self, moto_bucket):
        client = S3StorageClient()
        with pytest.raises(TypeError):
            client.upload_xml(uuid4(), uuid4(), 1, "<xml/>")  # type: ignore[arg-type]

    def test_nsu_negativo_rejeita(self, moto_bucket):
        client = S3StorageClient()
        with pytest.raises(ValueError):
            client.upload_xml(uuid4(), uuid4(), -1, b"x")


class TestUploadExport:
    def test_round_trip_com_bytes(self, moto_bucket):
        client = S3StorageClient()
        tid = uuid4()
        fid = uuid4()
        payload = b"PK\x03\x04fake zip"

        result = client.upload_export(tid, fid, payload, "zip")

        assert result.object_key == f"tenants-exports/{tid}/{fid}.zip"
        assert result.sha256 == hashlib.sha256(payload).hexdigest()
        obj = moto_bucket.get_object(Bucket=BUCKET, Key=result.object_key)
        assert obj["Body"].read() == payload
        assert obj["ContentType"] == "application/zip"

    def test_round_trip_com_path(self, moto_bucket, tmp_path):
        client = S3StorageClient()
        tid = uuid4()
        fid = uuid4()
        payload = b"\x50\x4b\x03\x04excel mock"
        fpath = tmp_path / "export.xlsx"
        fpath.write_bytes(payload)

        result = client.upload_export(tid, fid, fpath, "xlsx")

        assert result.object_key.endswith(".xlsx")
        assert result.sha256 == hashlib.sha256(payload).hexdigest()
        obj = moto_bucket.get_object(Bucket=BUCKET, Key=result.object_key)
        assert obj["ContentType"].endswith("spreadsheetml.sheet")
        assert obj["Body"].read() == payload

    def test_ext_desconhecida_usa_octet_stream(self, moto_bucket):
        client = S3StorageClient()
        result = client.upload_export(uuid4(), uuid4(), b"x", "bin")
        obj = moto_bucket.get_object(Bucket=BUCKET, Key=result.object_key)
        assert obj["ContentType"] == "application/octet-stream"

    def test_path_inexistente_vira_storage_error(self, moto_bucket):
        client = S3StorageClient()
        with pytest.raises(StorageError, match="nao foi possivel ler arquivo"):
            client.upload_export(
                uuid4(), uuid4(), "/tmp/nao-existe-nunca-xyz.bin", "bin"
            )


# ---------------------------------------------------------------------------
# Retry / falhas
# ---------------------------------------------------------------------------


def _client_error(code: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": code}}, "PutObject"
    )


class TestRetry:
    def test_is_transient(self):
        assert _is_transient(_client_error("SlowDown")) is True
        assert _is_transient(_client_error("ServiceUnavailable")) is True
        assert _is_transient(_client_error("InternalError")) is True
        assert _is_transient(
            EndpointConnectionError(endpoint_url="http://x")
        ) is True
        assert _is_transient(_client_error("AccessDenied")) is False
        assert _is_transient(_client_error("NoSuchBucket")) is False
        assert _is_transient(RuntimeError("boom")) is False

    def test_retry_sucede_apos_falhas_transientes(self, s3_env, monkeypatch):
        client = S3StorageClient()
        fake_s3 = MagicMock()
        calls = {"n": 0}

        def side_effect(**_kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise _client_error("SlowDown")
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

        fake_s3.put_object.side_effect = side_effect
        monkeypatch.setattr(client, "_client", lambda: fake_s3)
        # Corta o wait exponencial para o teste nao arrastar.
        monkeypatch.setattr(
            "worker_core.storage.wait_exponential",
            lambda **_kw: (lambda _rs: 0),
        )

        result = client.upload_xml(uuid4(), uuid4(), 1, b"<x/>")
        assert result.size == 4
        assert calls["n"] == 3

    def test_retry_esgota_em_erro_transiente(self, s3_env, monkeypatch):
        client = S3StorageClient()
        fake_s3 = MagicMock()
        fake_s3.put_object.side_effect = _client_error("SlowDown")
        monkeypatch.setattr(client, "_client", lambda: fake_s3)

        # Patch direto no `sleep` do tenacity via monkeypatch no time.sleep
        # que tenacity importa — caminho mais simples e fazer wait == 0.
        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(StorageError, match="SlowDown"):
                client.upload_xml(uuid4(), uuid4(), 1, b"<x/>")

        # 4 tentativas totais (stop_after_attempt=4).
        assert fake_s3.put_object.call_count == 4

    def test_erro_nao_transiente_nao_retry(self, s3_env, monkeypatch):
        client = S3StorageClient()
        fake_s3 = MagicMock()
        fake_s3.put_object.side_effect = _client_error("AccessDenied")
        monkeypatch.setattr(client, "_client", lambda: fake_s3)

        with pytest.raises(StorageError, match="AccessDenied"):
            client.upload_xml(uuid4(), uuid4(), 1, b"<x/>")

        # Unico PUT — sem retry para erro definitivo.
        assert fake_s3.put_object.call_count == 1

    def test_endpoint_connection_error_transiente(self, s3_env, monkeypatch):
        client = S3StorageClient()
        fake_s3 = MagicMock()
        fake_s3.put_object.side_effect = EndpointConnectionError(
            endpoint_url="http://x"
        )
        monkeypatch.setattr(client, "_client", lambda: fake_s3)

        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(StorageError, match="apos retries"):
                client.upload_xml(uuid4(), uuid4(), 1, b"<x/>")
        assert fake_s3.put_object.call_count == 4
