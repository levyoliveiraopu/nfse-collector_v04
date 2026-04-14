"""Testes unitarios do wrapper argon2id (API-02)."""

from __future__ import annotations

import logging

import pytest

from api.security.password import hash_password, needs_rehash, verify_password


def test_hash_is_argon2id_and_different_from_plain() -> None:
    plain = "correct horse battery staple"
    hashed = hash_password(plain)
    assert hashed != plain
    assert hashed.startswith("$argon2id$")


def test_verify_accepts_correct_password() -> None:
    plain = "correct horse battery staple"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True


def test_verify_rejects_wrong_password() -> None:
    hashed = hash_password("correct-password-123")
    assert verify_password("wrong-password", hashed) is False


def test_verify_rejects_empty_or_malformed() -> None:
    assert verify_password("", "whatever") is False
    assert verify_password("x", "") is False
    assert verify_password("x", "not-a-valid-argon2-hash") is False


def test_hash_rejects_empty_plain() -> None:
    with pytest.raises(ValueError):
        hash_password("")


def test_hash_output_is_non_deterministic() -> None:
    # Salt aleatorio: dois hashes da mesma senha sao diferentes.
    plain = "same-password"
    assert hash_password(plain) != hash_password(plain)


def test_needs_rehash_false_for_current_params() -> None:
    hashed = hash_password("abc12345678")
    assert needs_rehash(hashed) is False


def test_password_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Invariante de privacidade: plain nunca aparece em logs."""
    secret = "ultra-secret-passphrase-987"
    with caplog.at_level(logging.DEBUG):
        hashed = hash_password(secret)
        verify_password(secret, hashed)
        verify_password("bad", hashed)
    joined = " ".join(record.getMessage() for record in caplog.records)
    assert secret not in joined
