"""Camada de acesso ao Postgres (SQLAlchemy Core + Session).

Duas fabricas de sessao convivem porque o schema usa Row Level Security
(ADR-002 / DATA-01):

1. `get_admin_session()` — conecta com a role da migration (`app_admin`
   ou superuser), **BYPASSRLS**. Usado em fluxos que nao tem tenant_id
   definido ainda (ex.: `/auth/signup`, `/auth/login`).

2. `get_tenant_session(tenant_id)` — conecta com `app_user`
   (**NOBYPASSRLS**) e executa `SET LOCAL app.current_tenant = '<uuid>'`
   na mesma transacao. E o caminho padrao pos-auth: qualquer query
   enxerga apenas linhas do tenant corrente.

A URL base (`API_DATABASE_URL`) determina o usuario efetivo — o owner
configura uma URL por role quando quiser separar conexoes em prod.
Para simplificar v1, reusamos a mesma URL: o BYPASSRLS vem do role
ativo no cluster Postgres, nao do cliente.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError(
                "API_DATABASE_URL nao definida. Configure a URL do Postgres "
                "antes de chamar endpoints que usam o banco."
            )
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            future=True,
        )
        _SessionLocal = sessionmaker(
            bind=_engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _engine


def _get_sessionmaker() -> sessionmaker[Session]:
    _get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def reset_engine_for_tests() -> None:
    """Forca recriacao do engine no proximo uso. So deve ser chamado em testes."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


@contextmanager
def get_admin_session() -> Iterator[Session]:
    """Sessao sem filtro de tenant (BYPASSRLS via role do cluster).

    Usar apenas em fluxos de identidade (signup/login) e jobs de
    administracao. Nunca exponha essa sessao a handlers que recebem
    `tenant_id` do request.
    """
    session_factory = _get_sessionmaker()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_tenant_session(tenant_id: UUID | str) -> Iterator[Session]:
    """Sessao com `SET LOCAL app.current_tenant` — RLS ativa.

    A GUC e setada dentro da transacao atual; ao final do `with` o
    commit/rollback fecha a transacao e o escopo do `SET LOCAL` e
    perdido automaticamente, evitando vazamento entre requests.
    """
    session_factory = _get_sessionmaker()
    session = session_factory()
    try:
        # `SET LOCAL` precisa de transacao ativa: begin() explicito.
        with session.begin():
            session.execute(
                text("SET LOCAL app.current_tenant = :tid"),
                {"tid": str(tenant_id)},
            )
            yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
