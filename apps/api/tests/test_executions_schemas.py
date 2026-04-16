"""Testes unitarios dos schemas de `/executions` (API-07)."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from api.executions.schemas import (
    CreateExecutionsIn,
    CreateExecutionsOut,
    CreatedExecution,
    ExecutionOut,
)


def _sample(**overrides):
    base = {
        "company_ids": [uuid4()],
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 1, 31),
    }
    base.update(overrides)
    return base


def test_create_in_defaults_sao_manual_e_false() -> None:
    payload = CreateExecutionsIn(**_sample())
    assert payload.trigger == "manual"
    assert payload.dry_run is False


def test_create_in_aceita_trigger_explicito() -> None:
    payload = CreateExecutionsIn(**_sample(trigger="api"))
    assert payload.trigger == "api"


def test_create_in_recusa_trigger_invalido() -> None:
    with pytest.raises(ValidationError):
        CreateExecutionsIn(**_sample(trigger="adhoc"))


def test_create_in_recusa_period_end_antes_de_start() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CreateExecutionsIn(
            **_sample(
                period_start=date(2026, 2, 1),
                period_end=date(2026, 1, 31),
            )
        )
    assert "period_end" in str(exc_info.value)


def test_create_in_aceita_periodo_de_um_dia() -> None:
    payload = CreateExecutionsIn(
        **_sample(
            period_start=date(2026, 5, 10),
            period_end=date(2026, 5, 10),
        )
    )
    assert payload.period_start == payload.period_end


def test_create_in_deduplica_company_ids_preservando_ordem() -> None:
    cid_a, cid_b = uuid4(), uuid4()
    payload = CreateExecutionsIn(
        **_sample(company_ids=[cid_a, cid_b, cid_a])
    )
    assert payload.company_ids == [cid_a, cid_b]


def test_create_in_recusa_company_ids_vazio() -> None:
    with pytest.raises(ValidationError):
        CreateExecutionsIn(**_sample(company_ids=[]))


def test_create_in_recusa_campo_extra() -> None:
    with pytest.raises(ValidationError):
        CreateExecutionsIn(**_sample(extra_field="nope"))


def test_create_in_recusa_mais_de_500_companies() -> None:
    with pytest.raises(ValidationError):
        CreateExecutionsIn(**_sample(company_ids=[uuid4() for _ in range(501)]))


def test_created_execution_aceita_job_id_ou_erro() -> None:
    cid = uuid4()
    eid = uuid4()
    ok = CreatedExecution(
        execution_id=eid,
        company_id=cid,
        status="queued",
        job_id="abc-123",
    )
    fail = CreatedExecution(
        execution_id=eid,
        company_id=cid,
        status="failed",
        enqueue_error="enqueue_failed",
    )
    assert ok.status == "queued" and ok.job_id == "abc-123"
    assert fail.status == "failed" and fail.enqueue_error == "enqueue_failed"


def test_create_out_envelope() -> None:
    cid = uuid4()
    eid = uuid4()
    out = CreateExecutionsOut(
        created=[
            CreatedExecution(
                execution_id=eid,
                company_id=cid,
                status="queued",
                job_id="abc",
            )
        ]
    )
    assert len(out.created) == 1
    assert out.created[0].job_id == "abc"


def test_execution_out_aceita_campos_opcionais_none() -> None:
    # Garante que o envelope aceita executions recem-criadas (queued,
    # sem started_at/finished_at ainda).
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    out = ExecutionOut(
        id=uuid4(),
        tenant_id=uuid4(),
        company_id=uuid4(),
        trigger="manual",
        status="queued",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        items_total=0,
        items_ok=0,
        items_fail=0,
        created_at=now,
        updated_at=now,
    )
    assert out.started_at is None
    assert out.finished_at is None
    assert out.triggered_by_user_id is None
