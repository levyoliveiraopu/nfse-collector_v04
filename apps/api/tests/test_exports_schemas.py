"""Testes unitarios dos schemas de `/exports` (API-15)."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from api.exports.schemas import (
    CreateExportIn,
    CreateExportOut,
    ExportOut,
)


def test_create_export_minimal_ok() -> None:
    payload = CreateExportIn(
        company_id=uuid4(),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )
    assert payload.kind == "zip_xml"  # default


def test_create_export_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CreateExportIn(
            company_id=uuid4(),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            extra_field="nope",  # type: ignore[call-arg]
        )


def test_create_export_rejects_invalid_period() -> None:
    with pytest.raises(ValidationError) as exc:
        CreateExportIn(
            company_id=uuid4(),
            period_start=date(2026, 2, 1),
            period_end=date(2026, 1, 31),
        )
    assert "period_end" in str(exc.value)


def test_create_export_same_day_ok() -> None:
    # Intervalo de 1 dia (start == end) e valido.
    d = date(2026, 3, 15)
    payload = CreateExportIn(company_id=uuid4(), period_start=d, period_end=d)
    assert payload.period_start == payload.period_end == d


def test_kind_only_accepts_zip_xml_hoje() -> None:
    with pytest.raises(ValidationError):
        CreateExportIn(
            company_id=uuid4(),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            kind="excel_consolidated",  # type: ignore[arg-type]
        )


def test_create_export_out_envelope() -> None:
    eid = uuid4()
    out = CreateExportOut(
        export_id=eid, status="queued", job_id="abc", enqueue_error=None
    )
    assert out.export_id == eid
    assert out.status == "queued"


def test_create_export_out_enqueue_failed_shape() -> None:
    out = CreateExportOut(
        export_id=uuid4(),
        status="failed",
        job_id=None,
        enqueue_error="enqueue_failed",
    )
    assert out.job_id is None
    assert out.enqueue_error == "enqueue_failed"


def test_export_out_requires_required_fields() -> None:
    with pytest.raises(ValidationError):
        ExportOut(  # type: ignore[call-arg]
            id=uuid4(),
            tenant_id=uuid4(),
            # faltando company_id e varios outros obrigatorios
        )
