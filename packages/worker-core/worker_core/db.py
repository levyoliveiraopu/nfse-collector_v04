"""Sessao SQLAlchemy do worker (API-13).

Mesmo padrao do `apps/api/api/db.py`, mas reimplementado aqui para que
`worker-core` nao dependa de `apps/api`. Le `DATABASE_URL` (ou
`API_DATABASE_URL` como fallback, para reuso do .env do monorepo) e
oferece:

- `get_admin_session()` — sessao sem filtro de tenant (BYPASSRLS via
  role do cluster). Usada no handler para abrir a tx inicial com
  `app.current_tenant` setado no GUC.

- `get_tenant_session(tenant_id)` — sessao com `SET LOCAL
  app.current_tenant = '<uuid>'` dentro da transacao, mesmo padrao da
  API; qualquer query enxerga apenas linhas do tenant corrente.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Callable, Iterator
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _resolve_database_url(env: dict[str, str] | None = None) -> str:
    src = env if env is not None else os.environ
    for key in ("WORKER_DATABASE_URL", "API_DATABASE_URL", "DATABASE_URL"):
        raw = (src.get(key) or "").strip()
        if raw:
            return raw
    raise RuntimeError(
        "DATABASE_URL nao definida. Configure WORKER_DATABASE_URL ou "
        "API_DATABASE_URL no .env do worker."
    )


def _get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        url = _resolve_database_url()
        _engine = create_engine(url, pool_pre_ping=True, future=True)
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
    """Forca recriacao do engine. So em testes."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def set_sessionmaker_for_tests(factory: sessionmaker[Session] | None) -> None:
    """Injeta um sessionmaker custom (ex.: apontando para test DB)."""
    global _SessionLocal, _engine
    _SessionLocal = factory
    if factory is not None:
        _engine = factory.kw.get("bind")


@contextmanager
def get_admin_session() -> Iterator[Session]:
    """Sessao sem filtro de tenant. Usar apenas em flows internos."""
    session = _get_sessionmaker()()
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
    """Sessao com `SET LOCAL app.current_tenant` — RLS ativa."""
    session = _get_sessionmaker()()
    try:
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


SessionFactory = Callable[[], Session]
