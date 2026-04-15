"""Testes do helper de storage S3 para credenciais (API-06).

Usa `moto` para simular o S3 sem rede real. Pulado se moto nao estiver
instalado (ambientes minimos de dev).
"""

from __future__ import annotations

import os
import uuid

import pytest

moto = pytest.importorskip("moto")
from moto import mock_aws  # noqa: E402

from api import config as config_module  # noqa: E402
from api import storage as storage_module  # noqa: E402


_TEST_BUCKET = "nfse-saas-test"


@pytest.fixture()
def s3_env():
    """Configura envs do bucket fake e injeta credenciais dummy."""
    os.environ["S3_BUCKET"] = _TEST_BUCKET
    os.environ["S3_REGION"] = "us-east-1"
    os.environ["S3_KEY_ID"] = "test-key"
    os.environ["S3_APPLICATION_KEY"] = "test-secret"
    # moto nao precisa de endpoint customizado quando o cliente usa
    # AWS-default; deixamos vazio para simular um S3 nativo.
    os.environ.pop("S3_ENDPOINT", None)
    os.environ["S3_FORCE_PATH_STYLE"] = "true"
    os.environ["S3_CREDENTIALS_PREFIX"] = "tenants-credentials/"
    os.environ.setdefault("API_ENVIRONMENT", "development")
    config_module.get_settings.cache_clear()  # type: ignore[attr-defined]
    storage_module.reset_client_for_tests()
    yield
    storage_module.reset_client_for_tests()


@pytest.fixture()
def s3_bucket(s3_env):
    with mock_aws():
        client = storage_module._get_s3_client()
        client.create_bucket(Bucket=_TEST_BUCKET)
        yield client


def test_object_key_layout(s3_env) -> None:
    tid = uuid.uuid4()
    cid = uuid.uuid4()
    key = storage_module.credential_object_key(tid, cid)
    assert key == f"tenants-credentials/{tid}/{cid}.pfx.enc"


def test_put_get_delete_round_trip(s3_bucket) -> None:
    tid = uuid.uuid4()
    cid = uuid.uuid4()
    payload = b"\x01" + b"\x00" * 12 + b"opaque-ciphertext-bytes"

    key = storage_module.put_credential_blob(tid, cid, payload)
    assert key.endswith(f"{cid}.pfx.enc")

    # GET devolve os mesmos bytes.
    got = storage_module.get_credential_blob(key)
    assert got == payload

    # DELETE remove e get devolve None.
    existed = storage_module.delete_credential_blob(key)
    assert existed is True
    assert storage_module.get_credential_blob(key) is None


def test_delete_inexistente_devolve_false(s3_bucket) -> None:
    existed = storage_module.delete_credential_blob(
        "tenants-credentials/00000000-0000-0000-0000-000000000000/missing.pfx.enc"
    )
    assert existed is False


def test_storage_error_em_bucket_inexistente(s3_env) -> None:
    # Sem mock_aws ativo, o boto3 dispara erro de credencial/conexao.
    # Usamos mock_aws + bucket NAO criado para forcar NoSuchBucket.
    with mock_aws():
        with pytest.raises(storage_module.StorageError):
            storage_module.put_credential_blob(uuid.uuid4(), uuid.uuid4(), b"x")
