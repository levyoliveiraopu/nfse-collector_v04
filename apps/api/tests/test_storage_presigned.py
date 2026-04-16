"""Testes do helper `generate_presigned_get_url` (API-11).

Usa `moto` para gerar a URL sem acesso a rede real. Pulado se moto nao
estiver instalado.
"""

from __future__ import annotations

import os

import pytest

moto = pytest.importorskip("moto")
from moto import mock_aws  # noqa: E402

from api import config as config_module  # noqa: E402
from api import storage as storage_module  # noqa: E402


_TEST_BUCKET = "nfse-saas-test"


@pytest.fixture()
def s3_env():
    os.environ["S3_BUCKET"] = _TEST_BUCKET
    os.environ["S3_REGION"] = "us-east-1"
    os.environ["S3_KEY_ID"] = "test-key"
    os.environ["S3_APPLICATION_KEY"] = "test-secret"
    os.environ.pop("S3_ENDPOINT", None)
    os.environ["S3_FORCE_PATH_STYLE"] = "true"
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


def test_presign_gera_url_com_ttl(s3_bucket) -> None:
    key = "tenants/abc/file.xml"
    url = storage_module.generate_presigned_get_url(key, expires_seconds=3600)

    # URL aponta para o bucket e para o object_key.
    assert _TEST_BUCKET in url
    assert key in url or "file.xml" in url  # path-style pode ou nao incluir prefix
    # Parametros obrigatorios da v4 signature.
    assert "X-Amz-Signature=" in url
    assert "X-Amz-Expires=3600" in url
    assert "X-Amz-Algorithm=" in url


def test_presign_default_ttl_3600(s3_bucket) -> None:
    url = storage_module.generate_presigned_get_url("tenants/abc/other.xml")
    assert "X-Amz-Expires=3600" in url


def test_presign_rejeita_key_vazia(s3_bucket) -> None:
    with pytest.raises(storage_module.StorageError):
        storage_module.generate_presigned_get_url("")


def test_presign_rejeita_ttl_invalido(s3_bucket) -> None:
    with pytest.raises(storage_module.StorageError):
        storage_module.generate_presigned_get_url("k", expires_seconds=0)
    with pytest.raises(storage_module.StorageError):
        storage_module.generate_presigned_get_url(
            "k", expires_seconds=8 * 24 * 3600
        )
