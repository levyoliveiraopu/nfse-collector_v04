"""Cifra simetrica AES-256-GCM para segredos por tenant (API-06).

Modelo de chaves (envelope encryption):

    KEK (Key Encryption Key, 32 bytes)
       |
       v   HKDF-SHA256(salt=b"nfse-saas/credential/v1", info=tenant_id_bytes)
       |
    DEK por tenant (32 bytes)
       |
       v   AES-256-GCM(nonce=12 bytes random, AAD=tenant_id_bytes)
       |
    ciphertext (versao + nonce + GCM ciphertext+tag)

Por que envelope:
- Limita o blast radius — comprometer o ciphertext de UM tenant nao
  expoe os demais (DEKs sao distintas).
- Permite rotacao futura de KEK sem re-cifrar tudo: basta envolver as
  DEKs antigas (v1 -> v2). O `version_tag` no formato do ciphertext
  garante compat retroativa.

Alinhado com ADR-003: "cifra PFX AES-GCM" na camada da aplicacao;
chave nunca toca o banco.
"""

from __future__ import annotations

import base64
import logging
import os
from functools import lru_cache
from uuid import UUID

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .config import get_settings

logger = logging.getLogger("api.crypto")

# Versao binaria do envelope. 1 byte permite ate 256 versoes (sobra).
# Toda alteracao no algoritmo (mudar GCM nonce length, KDF, etc) bumpa.
_VERSION_TAG = b"\x01"
_NONCE_LEN = 12  # AES-GCM standard nonce length (96 bits).
_TAG_LEN = 16  # AES-GCM authentication tag length (128 bits).
_HKDF_SALT = b"nfse-saas/credential/v1"
_DEK_LEN = 32  # AES-256.

# KEK fallback APENAS para development. Determinista, mas NAO segura —
# o `_validate_auth_secrets` em config.py aborta a startup em
# staging/production se `API_CREDENTIAL_KEK_B64` estiver vazio.
_DEV_KEK_FALLBACK = b"nfse-dev-kek-32bytes-do-not-use!"
assert len(_DEV_KEK_FALLBACK) == 32


class CryptoError(Exception):
    """Erro generico de cifra/decifra. Mensagem nao expoe detalhes."""


def _load_kek() -> bytes:
    """Carrega a KEK do settings. Mascarada nos logs."""
    settings = get_settings()
    raw = settings.credential_kek_b64.strip()
    if not raw:
        if settings.environment != "development":
            # Defesa em profundidade — a config ja valida isso na startup,
            # mas reforcamos aqui pois testes podem instanciar Settings()
            # sem passar pelo singleton.
            raise CryptoError("KEK ausente em ambiente nao-development")
        logger.warning(
            "crypto.kek.dev_fallback",
            extra={"environment": settings.environment},
        )
        return _DEV_KEK_FALLBACK

    # Aceita base64 url-safe com ou sem padding.
    padded = raw + "=" * (-len(raw) % 4)
    try:
        kek = base64.urlsafe_b64decode(padded)
    except (ValueError, base64.binascii.Error) as exc:
        raise CryptoError("KEK invalida (base64 mal-formado)") from exc

    if len(kek) != 32:
        raise CryptoError(
            f"KEK deve ter 32 bytes apos decodificar (recebido: {len(kek)})"
        )
    return kek


@lru_cache(maxsize=512)
def _derive_dek(tenant_id_str: str) -> bytes:
    """Deriva DEK por tenant via HKDF-SHA256(KEK).

    Cache por processo: HKDF e CPU-bound suficiente para nao queremos
    repetir a derivacao a cada request. Limite de 512 entradas evita
    crescimento sem teto em multi-tenant grande.
    """
    kek = _load_kek()
    # Normaliza para garantir que o input do HKDF seja deterministico.
    tid = UUID(tenant_id_str).bytes  # 16 bytes canonicos.
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=_DEK_LEN,
        salt=_HKDF_SALT,
        info=tid,
    )
    return hkdf.derive(kek)


def encrypt(plaintext: bytes, tenant_id: UUID | str) -> bytes:
    """Cifra `plaintext` com AES-256-GCM e DEK derivada para `tenant_id`.

    Formato retornado: `version (1B) || nonce (12B) || ciphertext+tag`.
    AAD (additional authenticated data) = bytes UUID do tenant — protege
    contra "mover" um ciphertext de um tenant para outro.
    """
    if not isinstance(plaintext, (bytes, bytearray)):
        raise TypeError("plaintext deve ser bytes")
    if isinstance(tenant_id, UUID):
        tid_str = str(tenant_id)
    else:
        tid_str = str(UUID(str(tenant_id)))  # valida formato.

    dek = _derive_dek(tid_str)
    aead = AESGCM(dek)
    nonce = os.urandom(_NONCE_LEN)
    aad = UUID(tid_str).bytes
    ct = aead.encrypt(nonce, bytes(plaintext), aad)
    return _VERSION_TAG + nonce + ct


def decrypt(ciphertext: bytes, tenant_id: UUID | str) -> bytes:
    """Decifra um blob produzido por `encrypt`. Levanta `CryptoError` em qualquer falha."""
    if not isinstance(ciphertext, (bytes, bytearray)):
        raise CryptoError("ciphertext deve ser bytes")
    blob = bytes(ciphertext)
    if len(blob) < 1 + _NONCE_LEN + _TAG_LEN:
        raise CryptoError("ciphertext truncado")
    version = blob[:1]
    if version != _VERSION_TAG:
        raise CryptoError(f"versao de envelope desconhecida: {version!r}")

    nonce = blob[1 : 1 + _NONCE_LEN]
    ct = blob[1 + _NONCE_LEN :]

    if isinstance(tenant_id, UUID):
        tid_str = str(tenant_id)
    else:
        try:
            tid_str = str(UUID(str(tenant_id)))
        except (ValueError, AttributeError) as exc:
            raise CryptoError("tenant_id invalido") from exc

    dek = _derive_dek(tid_str)
    aad = UUID(tid_str).bytes
    aead = AESGCM(dek)
    try:
        return aead.decrypt(nonce, ct, aad)
    except Exception as exc:  # noqa: BLE001 — InvalidTag e variantes
        # Mensagem generica intencional: nao revela se foi tag invalida,
        # tenant errado, ou bytes corrompidos.
        raise CryptoError("falha ao decifrar ciphertext") from exc


def reset_kek_cache_for_tests() -> None:
    """Limpa o cache de DEKs. Apenas para uso em testes."""
    _derive_dek.cache_clear()
