"""Refresh tokens opacos (API-02).

- O token em claro e devolvido ao cliente uma vez so (no login/refresh).
- O banco guarda apenas o `token_hash` SHA-256 hex (tabela
  `refresh_tokens`, migration 0010). Isso significa que comprometer o
  banco nao permite forjar sessoes: para revogar basta marcar
  `revoked_at`.
- Rotacao: cada uso de `/auth/refresh` marca o token atual como
  revogado e cria um novo. `replaced_by` liga os dois registros.
- Detecao de reuso: se o cliente apresentar um refresh ja revogado,
  toda a cadeia derivada dele (via `replaced_by`) e revogada
  imediatamente — comportamento recomendado pela OWASP para mitigar
  roubo de refresh.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import Settings, get_settings


class RefreshTokenError(Exception):
    """Falha ao emitir/validar/rotacionar um refresh token."""


class RefreshTokenReused(RefreshTokenError):
    """Tentativa de uso de refresh ja revogado — cadeia invalidada."""


@dataclass(frozen=True)
class IssuedRefresh:
    id: UUID
    plain: str
    expires_at: datetime


def _hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def _generate_opaque_token() -> str:
    # 32 bytes = 256 bits de entropia; url-safe sem padding.
    return secrets.token_urlsafe(32)


def issue_refresh_token(
    session: Session,
    *,
    tenant_id: UUID,
    user_id: UUID,
    user_agent: Optional[str] = None,
    ip: Optional[str] = None,
    settings: Settings | None = None,
) -> IssuedRefresh:
    settings = settings or get_settings()
    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(days=settings.refresh_token_ttl_days)
    plain = _generate_opaque_token()
    token_hash = _hash_token(plain)

    row = session.execute(
        text(
            """
            INSERT INTO refresh_tokens
                (tenant_id, user_id, token_hash, expires_at, user_agent, ip)
            VALUES
                (:tenant_id, :user_id, :token_hash, :expires_at, :ua, :ip)
            RETURNING id
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "token_hash": token_hash,
            "expires_at": expires_at,
            "ua": user_agent,
            "ip": ip,
        },
    ).one()
    return IssuedRefresh(id=row.id, plain=plain, expires_at=expires_at)


def _revoke_chain(session: Session, start_id: UUID) -> None:
    """Revoga o token e todos os descendentes via `replaced_by`."""
    session.execute(
        text(
            """
            WITH RECURSIVE chain AS (
                SELECT id FROM refresh_tokens WHERE id = :rid
                UNION ALL
                SELECT rt.id
                FROM refresh_tokens rt
                JOIN chain c ON rt.replaced_by = c.id
            )
            UPDATE refresh_tokens
               SET revoked_at = COALESCE(revoked_at, now())
             WHERE id IN (SELECT id FROM chain)
            """
        ),
        {"rid": str(start_id)},
    )


def rotate_refresh_token(
    session: Session,
    *,
    plain: str,
    user_agent: Optional[str] = None,
    ip: Optional[str] = None,
    settings: Settings | None = None,
) -> tuple[UUID, UUID, IssuedRefresh]:
    """Valida `plain`, revoga o antigo e emite um novo par.

    Retorna `(tenant_id, user_id, novo_refresh)`.
    Levanta `RefreshTokenReused` se detectar uso de token ja revogado
    (toda a cadeia e invalidada como mitigacao).
    """
    if not plain:
        raise RefreshTokenError("refresh ausente")
    settings = settings or get_settings()
    token_hash = _hash_token(plain)

    row = session.execute(
        text(
            """
            SELECT id, tenant_id, user_id, revoked_at, expires_at
              FROM refresh_tokens
             WHERE token_hash = :th
            """
        ),
        {"th": token_hash},
    ).one_or_none()

    if row is None:
        raise RefreshTokenError("refresh desconhecido")

    now = datetime.now(tz=timezone.utc)
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if row.revoked_at is not None:
        # Reuso: invalida toda a cadeia derivada e recusa o pedido.
        _revoke_chain(session, row.id)
        raise RefreshTokenReused(
            "refresh ja revogado; cadeia invalidada"
        )

    if expires_at <= now:
        raise RefreshTokenError("refresh expirado")

    # Emite o novo token antes de revogar o antigo para poder setar
    # `replaced_by` corretamente.
    new_issued = issue_refresh_token(
        session,
        tenant_id=row.tenant_id,
        user_id=row.user_id,
        user_agent=user_agent,
        ip=ip,
        settings=settings,
    )
    session.execute(
        text(
            """
            UPDATE refresh_tokens
               SET revoked_at = now(),
                   replaced_by = :new_id
             WHERE id = :old_id
            """
        ),
        {"new_id": str(new_issued.id), "old_id": str(row.id)},
    )
    return row.tenant_id, row.user_id, new_issued


def revoke_refresh_token(session: Session, *, plain: str) -> bool:
    """Marca `plain` como revogado. Retorna True se algo foi revogado."""
    if not plain:
        return False
    token_hash = _hash_token(plain)
    result = session.execute(
        text(
            """
            UPDATE refresh_tokens
               SET revoked_at = now()
             WHERE token_hash = :th
               AND revoked_at IS NULL
            """
        ),
        {"th": token_hash},
    )
    return bool(result.rowcount)
