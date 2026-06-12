"""Unit tests de deduplicacao/idempotencia de /executions."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from api.executions.routes import _find_open_execution


class _Row:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _Result:
    def __init__(self, row):
        self._row = row

    def one_or_none(self):
        return self._row


class _FakeSession:
    def __init__(self, row):
        self.row = row
        self.calls: list[tuple[str, dict]] = []

    def execute(self, clause, params):
        self.calls.append((str(clause).lower(), dict(params)))
        return _Result(self.row)


def test_find_open_execution_busca_por_chave_idempotente() -> None:
    company_id = uuid4()
    execution_id = uuid4()
    session = _FakeSession(_Row(id=execution_id))

    found = _find_open_execution(
        session,  # type: ignore[arg-type]
        company_id=company_id,
        trigger="manual",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
    )

    assert found == execution_id
    sql, params = session.calls[0]
    assert "status in ('queued', 'running')" in sql
    assert "company_id = :cid" in sql
    assert params == {
        "cid": str(company_id),
        "trigger": "manual",
        "pstart": date(2026, 4, 1),
        "pend": date(2026, 4, 30),
    }
