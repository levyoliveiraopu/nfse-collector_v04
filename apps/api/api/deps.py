"""Dependencies FastAPI para autenticacao e sessao por tenant (API-03).

Este modulo materializa o "middleware de tenant" do ticket API-03 como
dependencies FastAPI encadeaveis — a forma idiomatica em FastAPI de
interceptar o ciclo de vida de uma request e propagar contexto ate o
handler. Middleware ASGI global nao foi escolhido porque rotas publicas
(`/health`, `/auth/signup`, `/auth/login`) precisam seguir sem token, e a
dependency-injection permite marcar rota a rota o que e protegido.

Fluxo de uma request protegida:

    request --> get_current_claims  (401 se faltar/invalido)
             -> assert_tenant_active (403 se nao existe/suspenso)
             -> get_tenant_db        (Session com app.current_tenant local)

Ativacao do RLS: `get_tenant_db` reusa `get_tenant_session(tenant_id)` do
`api.db`, que abre transacao com `set_config(..., true)`. A configuracao local
expira no commit/rollback, logo a conexao devolvida ao pool
**nao** carrega a GUC — condicao exigida no DoD do ticket.
"""

from __future__ import annotations

from typing import Iterator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import get_admin_session, get_tenant_session
from .security.jwt import AccessClaims, InvalidAccessToken, decode_access_token

# Status de tenant que bloqueiam o acesso (migration 0001 define o dominio
# completo como: trial, active, suspended, canceled).
_TENANT_BLOCKED_STATUSES = frozenset({"suspended", "canceled"})


def get_current_claims(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AccessClaims:
    """Extrai e valida o JWT do header `Authorization: Bearer <token>`.

    - Ausencia do header, esquema != Bearer ou token invalido -> 401.
    - Nao consulta o banco; apenas verifica assinatura/claims.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token ausente",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="esquema de autenticacao invalido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1].strip()
    try:
        return decode_access_token(token)
    except InvalidAccessToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token invalido",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def assert_tenant_active(
    claims: AccessClaims = Depends(get_current_claims),
) -> AccessClaims:
    """Garante que o tenant do JWT existe e nao esta suspenso/cancelado.

    Usa `get_admin_session` (BYPASSRLS) porque precisa ler `tenants` sem
    ainda ter setado a GUC — e o tenant pode nao existir (ex.: deletado
    apos emissao do token). Retorno: os mesmos claims, para a proxima
    dependency reaproveitar sem re-decodificar.
    """
    with get_admin_session() as session:
        row = session.execute(
            text("SELECT status FROM tenants WHERE id = :tid"),
            {"tid": str(claims.tid)},
        ).one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="tenant inexistente",
        )
    if row.status in _TENANT_BLOCKED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"tenant {row.status}",
        )
    return claims


def get_tenant_db(
    claims: AccessClaims = Depends(assert_tenant_active),
) -> Iterator[Session]:
    """Sessao SQLAlchemy com `app.current_tenant` local a transacao.

    Usa generator (nao context manager) para integrar com o ciclo de
    vida de dependencies FastAPI: o `yield` entrega a sessao ao handler,
    e o bloco apos o `yield` executa no teardown da request — o
    `with get_tenant_session(...)` garante commit ou rollback + close.
    """
    with get_tenant_session(claims.tid) as session:
        yield session
