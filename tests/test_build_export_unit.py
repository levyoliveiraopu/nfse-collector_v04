"""Testes unitarios do fluxo de export que nao dependem de Postgres/S3."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from uuid import UUID, uuid4

import pytest

from worker_core import jobs


def test_build_export_marks_running_with_export_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    export_id = uuid4()
    conn = object()
    running_calls: list[tuple[object, UUID]] = []
    empty_calls: list[tuple[object, UUID]] = []

    @contextmanager
    def fake_connect():
        yield conn

    export = jobs._ExportRow(
        id=export_id,
        tenant_id=uuid4(),
        company_id=uuid4(),
        kind="zip_xml",
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        status="queued",
        company_cnpj="40131594000194",
        company_name="PS CERTIFICADOS LTDA",
    )

    monkeypatch.setattr(jobs, "_connect", fake_connect)
    monkeypatch.setattr(jobs, "_load_export", lambda _conn, _eid: export)
    monkeypatch.setattr(
        jobs,
        "_mark_export_running",
        lambda received_conn, received_id: running_calls.append(
            (received_conn, received_id)
        ),
    )
    monkeypatch.setattr(jobs, "_list_items", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        jobs,
        "_mark_empty",
        lambda received_conn, received_id: empty_calls.append(
            (received_conn, received_id)
        ),
    )

    result = jobs.build_export(str(export_id), storage=object())

    assert result == {"status": "empty", "items": 0}
    assert running_calls == [(conn, export_id)]
    assert empty_calls == [(conn, export_id)]
