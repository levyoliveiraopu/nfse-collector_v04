"""Testes unitarios do envelope AES-GCM por tenant (API-06).

Roda sem `TEST_DATABASE_URL`: a cifra e puramente local (cryptography +
Settings). Validam:

- Round-trip (encrypt -> decrypt) preserva os bytes.
- Tenants diferentes derivam DEKs diferentes (AAD bate via UUID).
- Tampering em qualquer byte do ciphertext faz `decrypt` falhar.
- Versao de envelope `\\x01` e exigida — versao desconhecida = erro.
- Em `staging`/`production`, KEK ausente aborta a inicializacao.
- KEK invalida (base64 ruim ou tamanho != 32 bytes) -> CryptoError.
- Logs/excecoes nao expoem nem KEK nem plaintext.
"""

from __future__ import annotations

import base64
import os
import secrets
import uuid

import pytest

from api import config as config_module
from api import crypto as crypto_module


def _set_env(env: str, kek_b64: str | None) -> None:
    os.environ["API_ENVIRONMENT"] = env
    if kek_b64 is None:
        os.environ.pop("API_CREDENTIAL_KEK_B64", None)
    else:
        os.environ["API_CREDENTIAL_KEK_B64"] = kek_b64
    # JWT secret e necessario para Settings instanciar fora de development.
    os.environ.setdefault("API_JWT_SECRET", "x" * 48)
    config_module.get_settings.cache_clear()  # type: ignore[attr-defined]
    crypto_module.reset_kek_cache_for_tests()


@pytest.fixture()
def kek_dev() -> str:
    """Configura KEK valida em ambiente development."""
    kek = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    _set_env("development", kek)
    yield kek
    _set_env("development", None)


def test_round_trip_preserva_plaintext(kek_dev) -> None:
    tid = uuid.uuid4()
    plaintext = b"senha-do-pfx-com-acentuacao-cao-nao\xe9"
    ct = crypto_module.encrypt(plaintext, tid)
    assert ct[:1] == b"\x01"
    assert ct != plaintext  # nao volta plaintext
    out = crypto_module.decrypt(ct, tid)
    assert out == plaintext


def test_decrypt_com_tenant_errado_falha(kek_dev) -> None:
    tid_a = uuid.uuid4()
    tid_b = uuid.uuid4()
    ct = crypto_module.encrypt(b"hello", tid_a)
    with pytest.raises(crypto_module.CryptoError):
        crypto_module.decrypt(ct, tid_b)


def test_tampering_em_qualquer_byte_falha(kek_dev) -> None:
    tid = uuid.uuid4()
    ct = bytearray(crypto_module.encrypt(b"payload-tampering", tid))
    # Flipa um bit em uma posicao no meio do ciphertext.
    ct[len(ct) // 2] ^= 0x01
    with pytest.raises(crypto_module.CryptoError):
        crypto_module.decrypt(bytes(ct), tid)


def test_versao_desconhecida_rejeitada(kek_dev) -> None:
    tid = uuid.uuid4()
    ct = bytearray(crypto_module.encrypt(b"x", tid))
    ct[0] = 0x99  # versao desconhecida
    with pytest.raises(crypto_module.CryptoError):
        crypto_module.decrypt(bytes(ct), tid)


def test_ciphertext_truncado_falha(kek_dev) -> None:
    tid = uuid.uuid4()
    with pytest.raises(crypto_module.CryptoError):
        crypto_module.decrypt(b"\x01\x02\x03", tid)


def test_kek_ausente_em_production_aborta_settings() -> None:
    _set_env("production", None)
    try:
        with pytest.raises(Exception) as exc_info:
            config_module.get_settings()
        assert "KEK" in str(exc_info.value).upper() or "API_CREDENTIAL_KEK_B64" in str(exc_info.value)
    finally:
        _set_env("development", None)


def test_kek_invalida_base64_aborta_no_uso() -> None:
    _set_env("development", "@@@invalid-base64@@@!!!!")
    try:
        with pytest.raises(crypto_module.CryptoError):
            crypto_module.encrypt(b"x", uuid.uuid4())
    finally:
        _set_env("development", None)


def test_kek_tamanho_errado_aborta() -> None:
    short_kek = base64.urlsafe_b64encode(b"too-short").decode()
    _set_env("development", short_kek)
    try:
        with pytest.raises(crypto_module.CryptoError):
            crypto_module.encrypt(b"x", uuid.uuid4())
    finally:
        _set_env("development", None)


def test_dois_tenants_geram_dek_distintas(kek_dev) -> None:
    tid_a = uuid.uuid4()
    tid_b = uuid.uuid4()
    ct_a = crypto_module.encrypt(b"plaintext-comum", tid_a)
    ct_b = crypto_module.encrypt(b"plaintext-comum", tid_b)
    # Ciphertexts diferentes mesmo com mesmo plaintext (DEKs distintas + nonces).
    assert ct_a != ct_b
    # Cross-decrypt falha pelo AAD do GCM.
    with pytest.raises(crypto_module.CryptoError):
        crypto_module.decrypt(ct_a, tid_b)


def test_excecao_nao_expoe_plaintext(kek_dev, caplog) -> None:
    tid = uuid.uuid4()
    ct = crypto_module.encrypt(b"super-secreto-do-pfx", tid)
    with pytest.raises(crypto_module.CryptoError):
        crypto_module.decrypt(ct, uuid.uuid4())
    # Mensagem padrao deve ser generica.
    assert "super-secreto" not in caplog.text
