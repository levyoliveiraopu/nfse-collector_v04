"""Emissao e validacao de JWT de acesso (API-02).

- Algoritmo: HS256 (segredo unico em `API_JWT_SECRET`). Upgrade para
  RS256/KMS fica para quando houver gerencia de chaves dedicada.
- TTL: default 15 minutos (`API_ACCESS_TOKEN_TTL_MINUTES`).
- Claims minimos: `sub` (user_id), `tid` (tenant_id), `role`,
  `iat`, `exp`, `jti`, `iss`, `aud`.
- `decode_access_token` valida `iss`, `aud` e `exp`. Qualquer falha de
  assinatura/claim levanta `InvalidAccessToken`.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from ..config import Settings, get_settings


class InvalidAccessToken(Exception):
    """Token JWT rejeitado (assinatura, expiracao, claim ausente, etc.)."""


@dataclass(frozen=True)
class AccessClaims:
    sub: UUID  # user_id
    tid: UUID  # tenant_id
    role: str
    jti: str
    iat: datetime
    exp: datetime


def _effective_secret(settings: Settings) -> str:
    if settings.jwt_secret:
        return settings.jwt_secret
    # Em development toleramos segredo vazio com fallback deterministico
    # por processo. O validator em `Settings` ja bloqueia isso em prod.
    if settings.environment != "development":
        raise InvalidAccessToken(
            "API_JWT_SECRET ausente fora do ambiente de development"
        )
    return "dev-insecure-secret-do-not-use-in-prod"


def create_access_token(
    *,
    user_id: UUID | str,
    tenant_id: UUID | str,
    role: str,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    now = datetime.now(tz=timezone.utc)
    exp = now + timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": str(user_id),
        "tid": str(tenant_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, _effective_secret(settings), algorithm="HS256")


def decode_access_token(
    token: str, *, settings: Settings | None = None
) -> AccessClaims:
    settings = settings or get_settings()
    try:
        data = jwt.decode(
            token,
            _effective_secret(settings),
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "tid", "jti"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidAccessToken(str(exc)) from exc

    try:
        return AccessClaims(
            sub=UUID(str(data["sub"])),
            tid=UUID(str(data["tid"])),
            role=str(data.get("role", "")),
            jti=str(data["jti"]),
            iat=datetime.fromtimestamp(int(data["iat"]), tz=timezone.utc),
            exp=datetime.fromtimestamp(int(data["exp"]), tz=timezone.utc),
        )
    except (KeyError, ValueError) as exc:
        raise InvalidAccessToken(f"claim invalido: {exc}") from exc
