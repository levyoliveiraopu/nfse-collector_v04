"""Testes do emissor/validador de JWT de acesso (API-02)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt as pyjwt
import pytest

from api.config import Settings
from api.security.jwt import (
    InvalidAccessToken,
    create_access_token,
    decode_access_token,
)


def _settings(ttl_min: int = 15, secret: str = "unit-test-secret") -> Settings:
    return Settings(
        environment="development",
        jwt_secret=secret,
        access_token_ttl_minutes=ttl_min,
    )


def test_roundtrip_emits_and_decodes_claims() -> None:
    settings = _settings()
    user_id = uuid4()
    tenant_id = uuid4()
    token = create_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
        role="owner",
        settings=settings,
    )
    claims = decode_access_token(token, settings=settings)
    assert claims.sub == user_id
    assert claims.tid == tenant_id
    assert claims.role == "owner"
    assert claims.exp > datetime.now(tz=timezone.utc)
    assert claims.jti  # nao vazio


def test_decode_rejects_token_signed_with_wrong_secret() -> None:
    settings_a = _settings(secret="secret-A")
    settings_b = _settings(secret="secret-B")
    token = create_access_token(
        user_id=uuid4(),
        tenant_id=uuid4(),
        role="owner",
        settings=settings_a,
    )
    with pytest.raises(InvalidAccessToken):
        decode_access_token(token, settings=settings_b)


def test_decode_rejects_expired_token() -> None:
    settings = _settings()
    now = datetime.now(tz=timezone.utc)
    expired_payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": str(uuid4()),
        "tid": str(uuid4()),
        "role": "owner",
        "iat": int((now - timedelta(hours=2)).timestamp()),
        "exp": int((now - timedelta(hours=1)).timestamp()),
        "jti": "x" * 16,
    }
    token = pyjwt.encode(expired_payload, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(InvalidAccessToken):
        decode_access_token(token, settings=settings)


def test_decode_rejects_wrong_audience() -> None:
    settings = _settings()
    other = Settings(
        environment="development",
        jwt_secret=settings.jwt_secret,
        jwt_audience="other-aud",
    )
    token = create_access_token(
        user_id=uuid4(),
        tenant_id=uuid4(),
        role="owner",
        settings=settings,
    )
    with pytest.raises(InvalidAccessToken):
        decode_access_token(token, settings=other)


def test_prod_requires_secret() -> None:
    with pytest.raises(ValueError):
        Settings(environment="production", jwt_secret="")


def test_prod_rejects_short_secret() -> None:
    with pytest.raises(ValueError, match="pelo menos 32 bytes"):
        Settings(environment="production", jwt_secret="short-secret")
