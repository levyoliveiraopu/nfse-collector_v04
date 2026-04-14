"""Testes unitarios das dependencies de tenant (API-03).

Sem Postgres: mockamos `get_admin_session` e `decode_access_token` para
focar no contrato das dependencies (status codes, headers, delegacao
correta). Os testes E2E com RLS ativo ficam em
`test_tenant_middleware_integration.py`, gated por `TEST_DATABASE_URL`.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.deps import (
    _TENANT_BLOCKED_STATUSES,
    assert_tenant_active,
    get_current_claims,
)
from api.security.jwt import AccessClaims, InvalidAccessToken


def _make_claims(tid: str | None = None) -> AccessClaims:
    now = datetime.now(tz=timezone.utc)
    return AccessClaims(
        sub=uuid4(),
        tid=(uuid4() if tid is None else __import__("uuid").UUID(tid)),
        role="owner",
        jti="jti-test",
        iat=now,
        exp=now,
    )


# ---------------------------------------------------------------------------
# get_current_claims
# ---------------------------------------------------------------------------


def test_missing_authorization_header_raises_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_current_claims(authorization=None)
    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.parametrize(
    "header",
    [
        "",
        "Basic abc",
        "Bearer",
        "bearer ",
        "Token abc",
        "Bearer    ",
    ],
)
def test_malformed_authorization_header_raises_401(header: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_current_claims(authorization=header)
    assert exc_info.value.status_code == 401


def test_invalid_jwt_raises_401(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(token: str):  # noqa: ARG001
        raise InvalidAccessToken("expired")

    monkeypatch.setattr("api.deps.decode_access_token", _boom)
    with pytest.raises(HTTPException) as exc_info:
        get_current_claims(authorization="Bearer abc.def.ghi")
    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_valid_jwt_returns_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = _make_claims()
    monkeypatch.setattr("api.deps.decode_access_token", lambda token: expected)
    got = get_current_claims(authorization="Bearer x.y.z")
    assert got is expected


def test_bearer_scheme_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = _make_claims()
    monkeypatch.setattr("api.deps.decode_access_token", lambda token: expected)
    assert get_current_claims(authorization="bearer abc") is expected
    assert get_current_claims(authorization="BEARER abc") is expected


# ---------------------------------------------------------------------------
# assert_tenant_active
# ---------------------------------------------------------------------------


def _patch_admin_session(monkeypatch: pytest.MonkeyPatch, status_value: str | None):
    """Faz `get_admin_session()` devolver uma sessao que ao executar
    SELECT em `tenants` retorna `status_value` (ou None = nao existe)."""

    class _Result:
        def __init__(self, row) -> None:
            self._row = row

        def one_or_none(self):
            return self._row

    class _FakeSession:
        def execute(self, stmt, params):  # noqa: ARG002
            row = None if status_value is None else SimpleNamespace(status=status_value)
            return _Result(row)

    @contextmanager
    def _fake():
        yield _FakeSession()

    monkeypatch.setattr("api.deps.get_admin_session", _fake)


def test_tenant_inexistente_retorna_403(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_admin_session(monkeypatch, None)
    with pytest.raises(HTTPException) as exc_info:
        assert_tenant_active(claims=_make_claims())
    assert exc_info.value.status_code == 403
    assert "inexistente" in exc_info.value.detail


@pytest.mark.parametrize("status_value", sorted(_TENANT_BLOCKED_STATUSES))
def test_tenant_bloqueado_retorna_403(
    monkeypatch: pytest.MonkeyPatch, status_value: str
) -> None:
    _patch_admin_session(monkeypatch, status_value)
    with pytest.raises(HTTPException) as exc_info:
        assert_tenant_active(claims=_make_claims())
    assert exc_info.value.status_code == 403
    assert status_value in exc_info.value.detail


@pytest.mark.parametrize("status_value", ["active", "trial"])
def test_tenant_ativo_devolve_claims(
    monkeypatch: pytest.MonkeyPatch, status_value: str
) -> None:
    _patch_admin_session(monkeypatch, status_value)
    claims = _make_claims()
    assert assert_tenant_active(claims=claims) is claims
