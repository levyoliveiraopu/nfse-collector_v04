"""Hash de senha com argon2id (API-02).

Parametros default alinhados com a OWASP Password Storage Cheat Sheet
(argon2id, m=19 MiB, t=2, p=1). `argon2-cffi` embute os parametros no
hash resultante, entao podemos ajustar no futuro sem invalidar hashes
antigos — basta chamar `needs_rehash` no login e reescrever.

IMPORTANTE: as funcoes deste modulo NUNCA logam o `plain` recebido.
Qualquer mudanca aqui deve preservar essa invariante (testada em
`tests/test_auth_password.py`).
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

# Parametros OWASP 2024 para argon2id.
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19 * 1024,  # 19 MiB em KiB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


def hash_password(plain: str) -> str:
    """Produz um hash argon2id no formato padrao `$argon2id$v=19$...`."""
    if not isinstance(plain, str) or not plain:
        raise ValueError("senha vazia")
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica `plain` contra `hashed`. Retorna False em qualquer falha."""
    if not plain or not hashed:
        return False
    try:
        return _hasher.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError):
        return False
    except Exception:
        # Qualquer outra falha de parsing tambem nega o login.
        return False


def needs_rehash(hashed: str) -> bool:
    """Indica se o hash usa parametros desatualizados e deve ser regerado."""
    try:
        return _hasher.check_needs_rehash(hashed)
    except InvalidHashError:
        return True
