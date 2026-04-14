"""Testes unitarios do modulo de refresh tokens (API-02).

Cobrem as porcoes puras (geracao, hashing). Rotacao e revogacao sao
testadas no integracao Postgres (test_auth_routes_integration.py).
"""

from __future__ import annotations

from api.security.tokens import _generate_opaque_token, _hash_token


def test_generated_token_has_entropy() -> None:
    tokens = {_generate_opaque_token() for _ in range(100)}
    # 100 geracoes distintas — colisao indicaria entropia insuficiente.
    assert len(tokens) == 100
    for t in tokens:
        assert len(t) >= 32


def test_hash_is_deterministic_and_sha256_hex() -> None:
    plain = "sample-refresh-token-abc"
    h1 = _hash_token(plain)
    h2 = _hash_token(plain)
    assert h1 == h2
    # 256 bits em hex = 64 chars.
    assert len(h1) == 64
    int(h1, 16)  # parseavel como hex


def test_hash_differs_for_different_inputs() -> None:
    assert _hash_token("a") != _hash_token("b")
