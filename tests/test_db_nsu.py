"""Testes unitarios de `DbNsuSource` (API-13).

Usa uma sessao fake em lugar do Postgres real para exercitar a logica
pura (UPDATE only-if-greater, normalizacao de CNPJ, mismatch de CNPJ
-> 0, company missing -> 0). Integracao real vem nos testes E2E
gated por `TEST_DATABASE_URL`.
"""

from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

import pytest

from worker_core.db_nsu import DbNsuSource


class _FakeRow:
    def __init__(self, *, last_nsu, cnpj):
        self.last_nsu = last_nsu
        self.cnpj = cnpj


class _FakeExecResult:
    def __init__(self, *, row=None, rowcount: int = 0):
        self._row = row
        self.rowcount = rowcount

    def one_or_none(self):
        return self._row


class _FakeSession:
    def __init__(self, *, company_row=None):
        self._company_row = company_row
        self.calls: list[tuple[str, dict]] = []
        self.update_rowcount = 1

    def execute(self, clause, params):
        sql = str(clause).lower()
        self.calls.append((sql, params))
        if "update companies" in sql:
            return _FakeExecResult(rowcount=self.update_rowcount)
        return _FakeExecResult(row=self._company_row)


@contextmanager
def _make_factory(session: _FakeSession):
    def _factory(_tenant_id):
        @contextmanager
        def _cm():
            yield session
        return _cm()
    yield _factory


def test_get_retorna_last_nsu_quando_cnpj_bate() -> None:
    tid, cid = uuid4(), uuid4()
    sess = _FakeSession(company_row=_FakeRow(last_nsu=42, cnpj="12345678000199"))
    with _make_factory(sess) as factory:
        src = DbNsuSource(tenant_id=tid, company_id=cid, session_factory=factory)
        assert src.get("12345678000199") == 42


def test_get_retorna_zero_quando_company_nao_existe() -> None:
    tid, cid = uuid4(), uuid4()
    sess = _FakeSession(company_row=None)
    with _make_factory(sess) as factory:
        src = DbNsuSource(tenant_id=tid, company_id=cid, session_factory=factory)
        assert src.get("12345678000199") == 0


def test_get_retorna_zero_quando_cnpj_nao_bate() -> None:
    tid, cid = uuid4(), uuid4()
    sess = _FakeSession(company_row=_FakeRow(last_nsu=99, cnpj="99999999999999"))
    with _make_factory(sess) as factory:
        src = DbNsuSource(tenant_id=tid, company_id=cid, session_factory=factory)
        assert src.get("12345678000199") == 0


def test_get_aceita_cnpj_com_mascara() -> None:
    tid, cid = uuid4(), uuid4()
    sess = _FakeSession(company_row=_FakeRow(last_nsu=7, cnpj="12345678000199"))
    with _make_factory(sess) as factory:
        src = DbNsuSource(tenant_id=tid, company_id=cid, session_factory=factory)
        assert src.get("12.345.678/0001-99") == 7


def test_get_retorna_zero_quando_last_nsu_null() -> None:
    tid, cid = uuid4(), uuid4()
    sess = _FakeSession(company_row=_FakeRow(last_nsu=None, cnpj="12345678000199"))
    with _make_factory(sess) as factory:
        src = DbNsuSource(tenant_id=tid, company_id=cid, session_factory=factory)
        assert src.get("12345678000199") == 0


def test_set_emite_update_com_filtro_only_if_greater() -> None:
    tid, cid = uuid4(), uuid4()
    sess = _FakeSession()
    with _make_factory(sess) as factory:
        src = DbNsuSource(tenant_id=tid, company_id=cid, session_factory=factory)
        src.set("12345678000199", 100)

    updates = [call for call in sess.calls if "update companies" in call[0]]
    assert len(updates) == 1
    sql, params = updates[0]
    assert "last_nsu < :nsu" in sql or "last_nsu is null" in sql
    assert params["nsu"] == 100
    assert params["cnpj"] == "12345678000199"
    assert params["cid"] == str(cid)


def test_set_rejeita_nsu_negativo() -> None:
    tid, cid = uuid4(), uuid4()
    sess = _FakeSession()
    with _make_factory(sess) as factory:
        src = DbNsuSource(tenant_id=tid, company_id=cid, session_factory=factory)
        with pytest.raises(ValueError, match="nsu"):
            src.set("12345678000199", -1)


def test_set_rejeita_bool() -> None:
    tid, cid = uuid4(), uuid4()
    sess = _FakeSession()
    with _make_factory(sess) as factory:
        src = DbNsuSource(tenant_id=tid, company_id=cid, session_factory=factory)
        with pytest.raises(ValueError):
            src.set("12345678000199", True)  # type: ignore[arg-type]


def test_set_noop_quando_rowcount_zero() -> None:
    tid, cid = uuid4(), uuid4()
    sess = _FakeSession()
    sess.update_rowcount = 0  # simula "last_nsu ja maior ou igual"
    with _make_factory(sess) as factory:
        src = DbNsuSource(tenant_id=tid, company_id=cid, session_factory=factory)
        src.set("12345678000199", 5)
    updates = [c for c in sess.calls if "update companies" in c[0]]
    assert len(updates) == 1  # emite o UPDATE, mas nao levanta
