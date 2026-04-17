"""Testes unitarios dos schemas do /reprocess (API-10).

Nao exige Postgres — so valida o contrato de `ReprocessIn` e helpers
(`scope_kind`, `to_scope_json`).
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from api.reprocess.schemas import (
    ReprocessIn,
    ReprocessPeriod,
)


# ---------------------------------------------------------------------------
# Escopo 1 — execution_item_ids
# ---------------------------------------------------------------------------


def test_items_scope_valido():
    iid = uuid4()
    payload = ReprocessIn(execution_item_ids=[iid])
    assert payload.scope_kind() == "items"
    assert payload.to_scope_json() == {
        "kind": "items",
        "execution_item_ids": [str(iid)],
    }


def test_items_scope_dedup():
    iid = uuid4()
    payload = ReprocessIn(execution_item_ids=[iid, iid])
    assert payload.execution_item_ids == [iid]


def test_items_scope_vazio_422():
    with pytest.raises(ValidationError):
        ReprocessIn(execution_item_ids=[])


def test_items_scope_proibe_company_id():
    with pytest.raises(ValidationError, match="nao aceita"):
        ReprocessIn(
            execution_item_ids=[uuid4()],
            company_id=uuid4(),
        )


def test_items_scope_proibe_nsus():
    with pytest.raises(ValidationError, match="nao aceita"):
        ReprocessIn(
            execution_item_ids=[uuid4()],
            nsus=[1],
        )


# ---------------------------------------------------------------------------
# Escopo 2 — nsus
# ---------------------------------------------------------------------------


def test_nsus_scope_valido():
    cid = uuid4()
    payload = ReprocessIn(company_id=cid, nsus=[10, 11, 12])
    assert payload.scope_kind() == "nsus"
    assert payload.to_scope_json() == {
        "kind": "nsus",
        "company_id": str(cid),
        "nsus": [10, 11, 12],
    }


def test_nsus_scope_dedup():
    payload = ReprocessIn(company_id=uuid4(), nsus=[1, 1, 2, 2, 3])
    assert payload.nsus == [1, 2, 3]


def test_nsus_scope_negativo_422():
    with pytest.raises(ValidationError, match=">= 0"):
        ReprocessIn(company_id=uuid4(), nsus=[-1])


def test_nsus_scope_vazio_422():
    with pytest.raises(ValidationError):
        ReprocessIn(company_id=uuid4(), nsus=[])


def test_nsus_scope_sem_company_id_422():
    with pytest.raises(ValidationError, match="exatamente 1 escopo"):
        ReprocessIn(nsus=[1, 2])


def test_nsus_scope_proibe_period():
    with pytest.raises(ValidationError, match="nao aceita"):
        ReprocessIn(
            company_id=uuid4(),
            nsus=[1],
            period=ReprocessPeriod(start=date(2026, 1, 1), end=date(2026, 1, 31)),
        )


# ---------------------------------------------------------------------------
# Escopo 3 — period
# ---------------------------------------------------------------------------


def test_period_scope_valido():
    cid = uuid4()
    payload = ReprocessIn(
        company_id=cid,
        period=ReprocessPeriod(start=date(2026, 1, 1), end=date(2026, 1, 31)),
        statuses=["failed"],
    )
    assert payload.scope_kind() == "period"
    assert payload.to_scope_json() == {
        "kind": "period",
        "company_id": str(cid),
        "period": {"start": "2026-01-01", "end": "2026-01-31"},
        "statuses": ["failed"],
    }


def test_period_scope_sem_statuses_ok():
    """`statuses` e opcional — ausencia nao invalida o payload."""
    cid = uuid4()
    payload = ReprocessIn(
        company_id=cid,
        period=ReprocessPeriod(start=date(2026, 2, 1), end=date(2026, 2, 28)),
    )
    assert payload.scope_kind() == "period"
    assert "statuses" not in payload.to_scope_json()


def test_period_scope_sem_company_id_422():
    with pytest.raises(ValidationError, match="exatamente 1 escopo"):
        ReprocessIn(
            period=ReprocessPeriod(start=date(2026, 1, 1), end=date(2026, 1, 31)),
        )


def test_period_invalido_end_menor_que_start():
    with pytest.raises(ValidationError, match=">= period.start"):
        ReprocessIn(
            company_id=uuid4(),
            period=ReprocessPeriod(start=date(2026, 1, 31), end=date(2026, 1, 1)),
        )


def test_period_scope_status_invalido_422():
    with pytest.raises(ValidationError):
        ReprocessIn(
            company_id=uuid4(),
            period=ReprocessPeriod(start=date(2026, 1, 1), end=date(2026, 1, 31)),
            statuses=["fail"],  # domain canonico e "failed"
        )


def test_period_scope_statuses_dedup():
    cid = uuid4()
    payload = ReprocessIn(
        company_id=cid,
        period=ReprocessPeriod(start=date(2026, 1, 1), end=date(2026, 1, 31)),
        statuses=["failed", "failed", "ok"],
    )
    assert payload.statuses == ["failed", "ok"]


# ---------------------------------------------------------------------------
# Escopo unico
# ---------------------------------------------------------------------------


def test_payload_vazio_422():
    with pytest.raises(ValidationError, match="exatamente 1 escopo"):
        ReprocessIn()


def test_items_e_period_simultaneos_422():
    with pytest.raises(ValidationError, match="exatamente 1 escopo"):
        ReprocessIn(
            execution_item_ids=[uuid4()],
            company_id=uuid4(),
            period=ReprocessPeriod(start=date(2026, 1, 1), end=date(2026, 1, 31)),
        )


def test_extra_forbid_barra_campo_desconhecido():
    with pytest.raises(ValidationError):
        ReprocessIn.model_validate(
            {
                "execution_item_ids": [str(uuid4())],
                "unknown_field": True,
            }
        )


def test_dry_run_default_false():
    payload = ReprocessIn(execution_item_ids=[uuid4()])
    assert payload.dry_run is False


def test_dry_run_true_propaga():
    payload = ReprocessIn(execution_item_ids=[uuid4()], dry_run=True)
    assert payload.dry_run is True
