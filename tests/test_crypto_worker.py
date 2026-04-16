"""Testes do envelope AES-GCM do worker (API-13).

O handler do worker precisa decifrar ciphertext produzido pela API
(`apps/api/api/crypto.py`, API-06). Essa suite prova que o envelope e
interoperavel:

- Decifra cleanly um ciphertext gerado com o mesmo envelope.
- Tenant errado falha (AAD check do GCM).
- Versao desconhecida falha.
- Tamanho minimo do blob e checado.
- KEK ausente em staging/production aborta.
- KEK base64 invalida/tamanho errado -> CryptoError.

Nao exige DB nem Redis — pura cifra local.
"""

from __future__ import annotations

import base64
import os
import secrets
from uuid import UUID, uuid4

import pytest

from worker_core import crypto as worker_crypto
from worker_core.crypto import CryptoError, decrypt, reset_kek_cache_for_tests


# Reproduzimos em laboratorio o lado "encrypt" da API para nao importar
# apps/api dentro do teste de um pacote. Formato: version || nonce || GCM ct+tag.
def _encrypt(plaintext: bytes, tenant_id: UUID, *, version: bytes = b"\x01") -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    kek_b64 = os.environ["API_CREDENTIAL_KEK_B64"]
    padded = kek_b64 + "=" * (-len(kek_b64) % 4)
    kek = base64.urlsafe_b64decode(padded)
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"nfse-saas/credential/v1",
        info=tenant_id.bytes,
    )
    dek = hkdf.derive(kek)
    aead = AESGCM(dek)
    nonce = os.urandom(12)
    ct = aead.encrypt(nonce, plaintext, tenant_id.bytes)
    return version + nonce + ct


@pytest.fixture()
def kek_dev():
    kek = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    prev_kek = os.environ.get("API_CREDENTIAL_KEK_B64")
    prev_env = os.environ.get("API_ENVIRONMENT")
    os.environ["API_CREDENTIAL_KEK_B64"] = kek
    os.environ["API_ENVIRONMENT"] = "development"
    reset_kek_cache_for_tests()
    yield kek
    if prev_kek is None:
        os.environ.pop("API_CREDENTIAL_KEK_B64", None)
    else:
        os.environ["API_CREDENTIAL_KEK_B64"] = prev_kek
    if prev_env is None:
        os.environ.pop("API_ENVIRONMENT", None)
    else:
        os.environ["API_ENVIRONMENT"] = prev_env
    reset_kek_cache_for_tests()


def test_decrypt_round_trip(kek_dev) -> None:
    tid = uuid4()
    plaintext = b"senha-do-pfx-com-acentuacao-cao-\xe9"
    ct = _encrypt(plaintext, tid)
    assert decrypt(ct, tid) == plaintext


def test_decrypt_tenant_errado_falha(kek_dev) -> None:
    tid_a, tid_b = uuid4(), uuid4()
    ct = _encrypt(b"segredo", tid_a)
    with pytest.raises(CryptoError):
        decrypt(ct, tid_b)


def test_decrypt_versao_desconhecida_falha(kek_dev) -> None:
    tid = uuid4()
    ct = _encrypt(b"segredo", tid, version=b"\x02")
    with pytest.raises(CryptoError, match="versao"):
        decrypt(ct, tid)


def test_decrypt_ciphertext_truncado_falha(kek_dev) -> None:
    with pytest.raises(CryptoError, match="truncado"):
        decrypt(b"\x01\x00\x00", uuid4())


def test_decrypt_tamper_falha(kek_dev) -> None:
    tid = uuid4()
    ct = bytearray(_encrypt(b"segredo", tid))
    # Corrompe um byte no payload (evita o version tag em [0]).
    ct[20] ^= 0xFF
    with pytest.raises(CryptoError, match="decifrar"):
        decrypt(bytes(ct), tid)


def test_decrypt_ciphertext_nao_bytes_falha(kek_dev) -> None:
    with pytest.raises(CryptoError, match="bytes"):
        decrypt("nao-sao-bytes", uuid4())  # type: ignore[arg-type]


def test_decrypt_tenant_id_invalido_falha(kek_dev) -> None:
    tid = uuid4()
    ct = _encrypt(b"segredo", tid)
    with pytest.raises(CryptoError, match="tenant_id"):
        decrypt(ct, "nao-e-uuid")


def test_kek_ausente_em_production_aborta() -> None:
    prev_env = os.environ.get("API_ENVIRONMENT")
    prev_kek = os.environ.get("API_CREDENTIAL_KEK_B64")
    os.environ["API_ENVIRONMENT"] = "production"
    os.environ.pop("API_CREDENTIAL_KEK_B64", None)
    reset_kek_cache_for_tests()
    try:
        with pytest.raises(CryptoError, match="KEK ausente"):
            worker_crypto._load_kek()
    finally:
        if prev_env is None:
            os.environ.pop("API_ENVIRONMENT", None)
        else:
            os.environ["API_ENVIRONMENT"] = prev_env
        if prev_kek is not None:
            os.environ["API_CREDENTIAL_KEK_B64"] = prev_kek
        reset_kek_cache_for_tests()


def test_kek_base64_invalida_falha() -> None:
    prev_env = os.environ.get("API_ENVIRONMENT")
    prev_kek = os.environ.get("API_CREDENTIAL_KEK_B64")
    os.environ["API_ENVIRONMENT"] = "development"
    # Caracteres fora do alfabeto urlsafe_b64 com tamanho quebrado: o
    # `base64` levanta binascii.Error antes de chegar ao check de len.
    os.environ["API_CREDENTIAL_KEK_B64"] = "abc$%^&*"
    reset_kek_cache_for_tests()
    try:
        with pytest.raises(CryptoError):
            worker_crypto._load_kek()
    finally:
        if prev_env is None:
            os.environ.pop("API_ENVIRONMENT", None)
        else:
            os.environ["API_ENVIRONMENT"] = prev_env
        if prev_kek is None:
            os.environ.pop("API_CREDENTIAL_KEK_B64", None)
        else:
            os.environ["API_CREDENTIAL_KEK_B64"] = prev_kek
        reset_kek_cache_for_tests()


def test_kek_tamanho_errado_falha() -> None:
    prev_env = os.environ.get("API_ENVIRONMENT")
    prev_kek = os.environ.get("API_CREDENTIAL_KEK_B64")
    # 16 bytes em vez de 32.
    os.environ["API_ENVIRONMENT"] = "development"
    os.environ["API_CREDENTIAL_KEK_B64"] = base64.urlsafe_b64encode(b"x" * 16).decode()
    reset_kek_cache_for_tests()
    try:
        with pytest.raises(CryptoError, match="32 bytes"):
            worker_crypto._load_kek()
    finally:
        if prev_env is None:
            os.environ.pop("API_ENVIRONMENT", None)
        else:
            os.environ["API_ENVIRONMENT"] = prev_env
        if prev_kek is None:
            os.environ.pop("API_CREDENTIAL_KEK_B64", None)
        else:
            os.environ["API_CREDENTIAL_KEK_B64"] = prev_kek
        reset_kek_cache_for_tests()
