"""Testes unitarios dos schemas Pydantic de `/occurrences` (API-09)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from api.occurrences.schemas import (
    OccurrenceAssignIn,
    OccurrenceListOut,
    OccurrenceOut,
    OccurrenceResolveIn,
)


# ---------------------------------------------------------------------------
# OccurrenceResolveIn
# ---------------------------------------------------------------------------


def test_resolve_in_aceita_nota_simples() -> None:
    body = OccurrenceResolveIn(note="Cliente trocou a credencial.")
    assert body.note == "Cliente trocou a credencial."


def test_resolve_in_rejeita_nota_vazia() -> None:
    with pytest.raises(ValidationError):
        OccurrenceResolveIn(note="")


def test_resolve_in_rejeita_payload_extra() -> None:
    with pytest.raises(ValidationError):
        OccurrenceResolveIn(note="ok", status="resolved")  # type: ignore[call-arg]


def test_resolve_in_rejeita_nota_acima_do_teto() -> None:
    with pytest.raises(ValidationError):
        OccurrenceResolveIn(note="x" * 2001)


# ---------------------------------------------------------------------------
# OccurrenceAssignIn
# ---------------------------------------------------------------------------


def test_assign_in_aceita_uuid() -> None:
    uid = uuid4()
    body = OccurrenceAssignIn(assignee_user_id=uid)
    assert body.assignee_user_id == uid


def test_assign_in_rejeita_uuid_invalido() -> None:
    with pytest.raises(ValidationError):
        OccurrenceAssignIn(assignee_user_id="nao-e-uuid")  # type: ignore[arg-type]


def test_assign_in_rejeita_payload_extra() -> None:
    with pytest.raises(ValidationError):
        OccurrenceAssignIn(assignee_user_id=uuid4(), role="admin")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# OccurrenceOut / OccurrenceListOut (round-trip basico)
# ---------------------------------------------------------------------------


def _row(**overrides):
    """Mimica uma row do SQLAlchemy via SimpleNamespace-like dict."""
    base = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "company_id": uuid4(),
        "execution_id": None,
        "severity": "warning",
        "code": "CERT_EXPIRING",
        "title": "Certificado vence em 30 dias",
        "detail": None,
        "status": "open",
        "assignee_user_id": None,
        "first_seen_at": datetime.now(tz=timezone.utc),
        "last_seen_at": datetime.now(tz=timezone.utc),
        "resolved_at": None,
        "created_at": datetime.now(tz=timezone.utc),
        "updated_at": datetime.now(tz=timezone.utc),
    }
    base.update(overrides)
    return base


def test_occurrence_out_aceita_severity_e_status_validos() -> None:
    out = OccurrenceOut.model_validate(_row(severity="critical", status="ack"))
    assert out.severity == "critical"
    assert out.status == "ack"


def test_occurrence_out_rejeita_severity_invalida() -> None:
    with pytest.raises(ValidationError):
        OccurrenceOut.model_validate(_row(severity="fatal"))


def test_occurrence_out_rejeita_status_invalido() -> None:
    with pytest.raises(ValidationError):
        OccurrenceOut.model_validate(_row(status="closed"))


def test_occurrence_list_out_envelopa_total_e_paginacao() -> None:
    out = OccurrenceListOut(
        items=[OccurrenceOut.model_validate(_row())],
        page=1,
        page_size=20,
        total=1,
    )
    assert out.total == 1
    assert len(out.items) == 1
