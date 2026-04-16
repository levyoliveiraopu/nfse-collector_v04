"""Decifra AES-256-GCM do worker (API-13).

Espelha o envelope produzido por `apps/api/api/crypto.py` (API-06):

    ciphertext = version(1B) || nonce(12B) || GCM(ciphertext+tag)
    DEK        = HKDF-SHA256(KEK, salt="nfse-saas/credential/v1", info=uuid_bytes)
    AAD        = UUID(tenant_id).bytes

Fonte canonica do formato: ``apps/api/api/crypto.py``. Se aquele
modulo mudar (nova versao de envelope, novo salt, outro algoritmo), este
precisa acompanhar. O `_VERSION_TAG` protege contra drift silencioso: um
ciphertext cifrado pela API v2 nao vai abrir aqui com v1.

Por que duplicado: `worker-core` e um pacote independente (pode ser
instalado em um worker isolado sem a API). Compartilhar via import de
`apps/api` criaria acoplamento na direcao errada (pacote depende de app).
Extrair para um `packages/shared-crypto/` seria outro ticket.
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

logger = logging.getLogger("worker_core.crypto")

_VERSION_TAG = b"\x01"
_NONCE_LEN = 12
_TAG_LEN = 16
_HKDF_SALT = b"nfse-saas/credential/v1"
_DEK_LEN = 32

# Fallback determinista de dev. Abortamos em staging/prod.
_DEV_KEK_FALLBACK = b"nfse-dev-kek-32bytes-do-not-use!"
assert len(_DEV_KEK_FALLBACK) == 32


class CryptoError(Exception):
    """Erro generico de decifra. Mensagem nao expoe detalhes internos."""


def _load_kek(env: dict[str, str] | None = None) -> bytes:
    """Carrega a KEK da env `API_CREDENTIAL_KEK_B64`."""
    src = env if env is not None else os.environ
    raw = (src.get("API_CREDENTIAL_KEK_B64") or "").strip()
    environment = (src.get("API_ENVIRONMENT") or "development").strip().lower()
    if not raw:
        if environment != "development":
            raise CryptoError("KEK ausente em ambiente nao-development")
        logger.warning(
            "crypto.kek.dev_fallback",
            extra={"environment": environment},
        )
        return _DEV_KEK_FALLBACK

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
    """Deriva DEK por tenant via HKDF-SHA256(KEK)."""
    kek = _load_kek()
    tid = UUID(tenant_id_str).bytes
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=_DEK_LEN,
        salt=_HKDF_SALT,
        info=tid,
    )
    return hkdf.derive(kek)


def decrypt(ciphertext: bytes, tenant_id: UUID | str) -> bytes:
    """Decifra um blob produzido por `apps/api/api/crypto.encrypt`.

    Levanta `CryptoError` em qualquer falha (bytes curtos, versao
    desconhecida, tag invalida, tenant errado).
    """
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
    except Exception as exc:  # noqa: BLE001 - InvalidTag e variantes
        raise CryptoError("falha ao decifrar ciphertext") from exc


def reset_kek_cache_for_tests() -> None:
    """Limpa o cache de DEKs. So deve ser chamado em testes."""
    _derive_dek.cache_clear()
