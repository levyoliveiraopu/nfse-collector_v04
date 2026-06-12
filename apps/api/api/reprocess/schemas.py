"""Schemas Pydantic de `/reprocess` (API-10).

Tres escopos sao suportados no body de `POST /reprocess`, mutuamente
exclusivos:

1. `{"execution_item_ids": [...]}` — reprocessa items especificos; o
   handler agrupa por `(company_id, period_start, period_end)` da
   execution-pai e cria 1 execution filha por tupla distinta.
2. `{"company_id": "...", "nsus": [...]}` — reprocessa NSUs de uma
   unica company; o handler infere o periodo a partir do
   `MIN/MAX(data_emissao)` dos items existentes, com fallback defensivo
   para `[today, today]` quando nenhum item bate.
3. `{"company_id": "...", "period": {"start":..., "end":...},
   "statuses": ["failed",...]}` — reprocessa a janela inteira de uma
   company; `statuses` fica persistido em `reprocess_jobs.scope` como
   metadata auditavel (o worker atual ignora, pois refaz toda a janela
   — a idempotencia do unique parcial em `execution_items` trata
   duplicatas).

A validacao `model_validator` garante que exatamente **um** shape chega
ao handler. `extra='forbid'` em todos os schemas bloqueia campos nao
documentados.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Escopos
# ---------------------------------------------------------------------------


class ReprocessItemsScope(BaseModel):
    """Escopo 1 — lista de `execution_items.id`."""

    model_config = ConfigDict(extra="forbid")

    execution_item_ids: list[UUID] = Field(min_length=1, max_length=2_000)

    @field_validator("execution_item_ids")
    @classmethod
    def _dedup(cls, value: list[UUID]) -> list[UUID]:
        seen: set[UUID] = set()
        unique: list[UUID] = []
        for iid in value:
            if iid in seen:
                continue
            seen.add(iid)
            unique.append(iid)
        return unique


class ReprocessPeriod(BaseModel):
    """Janela de competencia (alias das datas de `executions`)."""

    model_config = ConfigDict(extra="forbid")

    start: date
    end: date

    @model_validator(mode="after")
    def _check(self) -> "ReprocessPeriod":
        if self.end < self.start:
            raise ValueError("period.end deve ser >= period.start")
        return self


# Status dos items aceitos no scope 3. Alinhado com
# `ck_execution_items_status` de `0005_execution_items`. O ticket
# sugere `["fail"]`; o dominio real usa `failed`, entao aceitamos o
# nome canonico.
ReprocessItemStatus = Literal["ok", "failed", "skipped", "pending"]


class ReprocessIn(BaseModel):
    """Payload de `POST /reprocess` — exatamente 1 dos 3 escopos."""

    model_config = ConfigDict(extra="forbid")

    # Escopo 1.
    execution_item_ids: Optional[list[UUID]] = Field(default=None, min_length=1, max_length=2_000)

    # Escopo 2/3 compartilham company_id.
    company_id: Optional[UUID] = Field(default=None)

    # Escopo 2.
    nsus: Optional[list[int]] = Field(default=None, min_length=1, max_length=2_000)

    # Escopo 3.
    period: Optional[ReprocessPeriod] = Field(default=None)
    statuses: Optional[list[ReprocessItemStatus]] = Field(default=None, min_length=1, max_length=10)

    # Comum aos 3 escopos. Propagado no meta do job RQ (mesmo padrao
    # de API-07 — nao persiste no schema).
    dry_run: bool = False

    @field_validator("execution_item_ids")
    @classmethod
    def _dedup_execution_item_ids(cls, value: Optional[list[UUID]]) -> Optional[list[UUID]]:
        if value is None:
            return value
        seen: set[UUID] = set()
        unique: list[UUID] = []
        for item_id in value:
            if item_id in seen:
                continue
            seen.add(item_id)
            unique.append(item_id)
        return unique

    @field_validator("nsus")
    @classmethod
    def _dedup_nsus(cls, value: Optional[list[int]]) -> Optional[list[int]]:
        if value is None:
            return value
        seen: set[int] = set()
        unique: list[int] = []
        for nsu in value:
            if nsu < 0:
                raise ValueError("nsus devem ser >= 0")
            if nsu in seen:
                continue
            seen.add(nsu)
            unique.append(nsu)
        return unique

    @field_validator("statuses")
    @classmethod
    def _dedup_statuses(cls, value: Optional[list[ReprocessItemStatus]]) -> Optional[list[ReprocessItemStatus]]:
        if value is None:
            return value
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def _exactly_one_scope(self) -> "ReprocessIn":
        by_items = self.execution_item_ids is not None
        by_nsus = self.company_id is not None and self.nsus is not None
        by_period = self.company_id is not None and self.period is not None

        # Mensagem especifica esperada para conflito entre os escopos 2 e 3.
        if by_nsus and (self.period is not None or self.statuses is not None):
            raise ValueError("escopo por nsus nao aceita period/statuses")

        matches = sum([by_items, by_nsus, by_period])
        if matches != 1:
            raise ValueError(
                "forneca exatamente 1 escopo: "
                "execution_item_ids | (company_id + nsus) | "
                "(company_id + period[ + statuses])"
            )

        if by_items and (
            self.company_id is not None or self.nsus is not None or self.period is not None or self.statuses is not None
        ):
            raise ValueError("escopo por execution_item_ids nao aceita company_id/nsus/period/statuses")
        if by_period and self.nsus is not None:
            raise ValueError("escopo por period nao aceita nsus")

        return self

    def scope_kind(self) -> Literal["items", "nsus", "period"]:
        if self.execution_item_ids is not None:
            return "items"
        if self.nsus is not None:
            return "nsus"
        return "period"

    def to_scope_json(self) -> dict:
        """Serializa o scope como JSON para gravar em `reprocess_jobs.scope`.

        Guarda somente o que o usuario enviou — campos nao relevantes
        ficam fora (e o `kind` canonico entra).
        """
        kind = self.scope_kind()
        if kind == "items":
            assert self.execution_item_ids is not None
            return {
                "kind": "items",
                "execution_item_ids": [str(i) for i in self.execution_item_ids],
            }
        if kind == "nsus":
            assert self.company_id is not None and self.nsus is not None
            return {
                "kind": "nsus",
                "company_id": str(self.company_id),
                "nsus": list(self.nsus),
            }
        assert self.company_id is not None and self.period is not None
        out: dict = {
            "kind": "period",
            "company_id": str(self.company_id),
            "period": {
                "start": self.period.start.isoformat(),
                "end": self.period.end.isoformat(),
            },
        }
        if self.statuses is not None:
            out["statuses"] = list(self.statuses)
        return out


# ---------------------------------------------------------------------------
# Respostas
# ---------------------------------------------------------------------------


class ReprocessChildExecution(BaseModel):
    """Item da resposta de POST /reprocess — 1 linha por execution filha."""

    execution_id: UUID
    company_id: UUID
    period_start: date
    period_end: date
    status: Literal["queued", "failed"]
    job_id: Optional[str] = None
    enqueue_error: Optional[str] = None


ReprocessJobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class ReprocessProgress(BaseModel):
    """Contagens agregadas das executions filhas (derivadas em GET)."""

    total: int
    queued: int
    running: int
    succeeded: int
    failed: int
    cancelled: int
    partial: int
    # Status efetivo derivado: `running` se alguma in-flight;
    # `succeeded`/`partial`/`failed`/`cancelled` apos todas terminarem.
    effective_status: Literal["queued", "running", "succeeded", "partial", "failed", "cancelled"]


class ReprocessOut(BaseModel):
    """Representacao retornada por POST e GET /reprocess/{id}."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    status: ReprocessJobStatus
    scope: dict
    result_execution_ids: list[UUID]
    error_summary: Optional[str] = None
    created_by_user_id: Optional[UUID] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # Preenchido apenas pelo POST (enfileiramento fresco).
    created_executions: Optional[list[ReprocessChildExecution]] = None
    # Preenchido apenas pelo GET (progress via agregacao).
    progress: Optional[ReprocessProgress] = None
