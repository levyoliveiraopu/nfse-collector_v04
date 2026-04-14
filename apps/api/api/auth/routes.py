"""Endpoints de autenticacao (API-02).

Fluxos suportados:

- `POST /auth/signup` — cria tenant + user + tenant_users(owner).
- `POST /auth/login` — verifica argon2id, emite access + refresh.
- `POST /auth/refresh` — rotaciona o refresh (detecao de reuso).
- `POST /auth/logout` — revoga o refresh apresentado.

Respostas de erro sao deliberadamente genericas (`401` + mensagem
neutra) para nao vazar existencia de email cadastrado.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..config import Settings, get_settings
from ..db import get_admin_session
from ..deps import assert_tenant_active, get_tenant_db
from ..security.jwt import AccessClaims, create_access_token
from ..security.password import hash_password, verify_password
from ..security.tokens import (
    RefreshTokenError,
    RefreshTokenReused,
    issue_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)
from .schemas import (
    AuthOut,
    LoginIn,
    LogoutIn,
    LogoutOut,
    MeOut,
    RefreshIn,
    SignupIn,
)

logger = logging.getLogger("api.auth")

# Limiter compartilhado; registrado no app em main.py.
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> Optional[str]:
    try:
        return get_remote_address(request)
    except Exception:
        return None


def _build_auth_out(
    *,
    access_token: str,
    refresh_plain: str,
    settings: Settings,
    tenant_id: str,
    user_id: str,
    role: str,
) -> AuthOut:
    return AuthOut(
        access_token=access_token,
        refresh_token=refresh_plain,
        expires_in=settings.access_token_ttl_minutes * 60,
        tenant_id=tenant_id,
        user_id=user_id,
        role=role,
    )


@router.post(
    "/signup",
    response_model=AuthOut,
    status_code=status.HTTP_201_CREATED,
)
def signup(
    payload: SignupIn,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> AuthOut:
    password_hash = hash_password(payload.password)
    user_agent = request.headers.get("user-agent")
    ip = _client_ip(request)

    try:
        with get_admin_session() as session:
            tenant_row = session.execute(
                text(
                    """
                    INSERT INTO tenants (name, slug)
                    VALUES (:name, :slug)
                    RETURNING id
                    """
                ),
                {"name": payload.tenant_name, "slug": payload.tenant_slug},
            ).one()
            tenant_id = tenant_row.id

            user_row = session.execute(
                text(
                    """
                    INSERT INTO users (email, password_hash, name, status)
                    VALUES (:email, :pw, :name, 'active')
                    RETURNING id
                    """
                ),
                {
                    "email": payload.email.lower(),
                    "pw": password_hash,
                    "name": payload.name,
                },
            ).one()
            user_id = user_row.id

            session.execute(
                text(
                    """
                    INSERT INTO tenant_users (tenant_id, user_id, role, accepted_at)
                    VALUES (:tid, :uid, 'owner', now())
                    """
                ),
                {"tid": str(tenant_id), "uid": str(user_id)},
            )

            refresh = issue_refresh_token(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                user_agent=user_agent,
                ip=ip,
                settings=settings,
            )
    except IntegrityError as exc:
        # Slug ou email ja usados: resposta generica para nao enumerar.
        logger.info(
            "auth.signup.conflict",
            extra={"error": exc.orig.__class__.__name__ if exc.orig else "IntegrityError"},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="tenant ou usuario ja existente",
        ) from exc

    access = create_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
        role="owner",
        settings=settings,
    )
    logger.info(
        "auth.signup.ok",
        extra={"tenant_id": str(tenant_id), "user_id": str(user_id)},
    )
    return _build_auth_out(
        access_token=access,
        refresh_plain=refresh.plain,
        settings=settings,
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        role="owner",
    )


@router.post("/login", response_model=AuthOut)
@limiter.limit(lambda: get_settings().login_rate_limit)
def login(
    request: Request,
    payload: LoginIn,
    settings: Settings = Depends(get_settings),
) -> AuthOut:
    user_agent = request.headers.get("user-agent")
    ip = _client_ip(request)
    # Mensagem generica em todas as falhas.
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="credenciais invalidas",
    )

    with get_admin_session() as session:
        row = session.execute(
            text(
                """
                SELECT u.id AS user_id,
                       u.password_hash,
                       u.status,
                       tu.tenant_id,
                       tu.role
                  FROM users u
                  JOIN tenant_users tu ON tu.user_id = u.id
                 WHERE LOWER(u.email) = LOWER(:email)
                 ORDER BY tu.accepted_at NULLS LAST
                 LIMIT 1
                """
            ),
            {"email": payload.email},
        ).one_or_none()

        if row is None:
            logger.info("auth.login.unknown_email")
            raise invalid_credentials

        if row.status != "active":
            logger.info(
                "auth.login.inactive",
                extra={"user_id": str(row.user_id), "status": row.status},
            )
            raise invalid_credentials

        if not verify_password(payload.password, row.password_hash):
            logger.info(
                "auth.login.bad_password",
                extra={"user_id": str(row.user_id)},
            )
            raise invalid_credentials

        session.execute(
            text("UPDATE users SET last_login_at = now() WHERE id = :uid"),
            {"uid": str(row.user_id)},
        )
        refresh = issue_refresh_token(
            session,
            tenant_id=row.tenant_id,
            user_id=row.user_id,
            user_agent=user_agent,
            ip=ip,
            settings=settings,
        )

    access = create_access_token(
        user_id=row.user_id,
        tenant_id=row.tenant_id,
        role=row.role,
        settings=settings,
    )
    logger.info(
        "auth.login.ok",
        extra={
            "tenant_id": str(row.tenant_id),
            "user_id": str(row.user_id),
        },
    )
    return _build_auth_out(
        access_token=access,
        refresh_plain=refresh.plain,
        settings=settings,
        tenant_id=str(row.tenant_id),
        user_id=str(row.user_id),
        role=row.role,
    )


@router.post("/refresh", response_model=AuthOut)
def refresh(
    payload: RefreshIn,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> AuthOut:
    user_agent = request.headers.get("user-agent")
    ip = _client_ip(request)

    try:
        with get_admin_session() as session:
            tenant_id, user_id, new_refresh = rotate_refresh_token(
                session,
                plain=payload.refresh_token,
                user_agent=user_agent,
                ip=ip,
                settings=settings,
            )
            role_row = session.execute(
                text(
                    """
                    SELECT role FROM tenant_users
                     WHERE tenant_id = :tid AND user_id = :uid
                    """
                ),
                {"tid": str(tenant_id), "uid": str(user_id)},
            ).one_or_none()
    except RefreshTokenReused as exc:
        logger.warning("auth.refresh.reuse_detected")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="refresh invalido",
        ) from exc
    except RefreshTokenError as exc:
        logger.info("auth.refresh.invalid", extra={"reason": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="refresh invalido",
        ) from exc

    if role_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="refresh invalido",
        )

    access = create_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role_row.role,
        settings=settings,
    )
    return _build_auth_out(
        access_token=access,
        refresh_plain=new_refresh.plain,
        settings=settings,
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        role=role_row.role,
    )


@router.post("/logout", response_model=LogoutOut)
def logout(payload: LogoutIn) -> LogoutOut:
    with get_admin_session() as session:
        ok = revoke_refresh_token(session, plain=payload.refresh_token)
    # Sempre 200, mesmo sem match — nao vazar se o token existia.
    return LogoutOut(revoked=ok)


@router.get("/me", response_model=MeOut)
def me(
    claims: AccessClaims = Depends(assert_tenant_active),
    db=Depends(get_tenant_db),
) -> MeOut:
    """Identidade corrente + prova de vida do middleware de tenant (API-03).

    Responde 200 apenas quando:
    - o JWT foi validado (`get_current_claims`);
    - o tenant existe e nao esta suspenso/cancelado (`assert_tenant_active`);
    - a sessao RLS-gated foi aberta (`get_tenant_db`) — a contagem em
      `tenant_users` comprova que as politicas RLS enxergam somente o
      tenant corrente.
    """
    count_row = db.execute(
        text(
            "SELECT COUNT(*) AS n FROM tenant_users WHERE user_id = :uid"
        ),
        {"uid": str(claims.sub)},
    ).one()
    return MeOut(
        tenant_id=str(claims.tid),
        user_id=str(claims.sub),
        role=claims.role,
        memberships_visible=int(count_row.n),
    )
