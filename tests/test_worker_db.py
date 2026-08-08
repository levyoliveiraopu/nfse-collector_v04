"""Contrato da sessao transacional do worker com RLS por tenant."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from uuid import uuid4

import pytest

from worker_core import db


class _FakeSession:
    def __init__(self) -> None:
        self.statements: list[tuple[str, dict[str, str]]] = []
        self.closed = False

    @contextmanager
    def begin(self) -> Iterator[None]:
        yield

    def execute(self, statement: object, params: dict[str, str]) -> None:
        self.statements.append((str(statement), params))

    def rollback(self) -> None:
        raise AssertionError("rollback inesperado")

    def close(self) -> None:
        self.closed = True


def test_tenant_session_uses_parameterized_transaction_local_guc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    tenant_id = uuid4()
    monkeypatch.setattr(db, "_get_sessionmaker", lambda: lambda: session)

    with db.get_tenant_session(tenant_id) as yielded:
        assert yielded is session

    assert session.statements == [
        (
            "SELECT set_config('app.current_tenant', :tid, true)",
            {"tid": str(tenant_id)},
        )
    ]
    assert session.closed is True
