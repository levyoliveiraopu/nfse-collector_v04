"""Schemas Pydantic dos endpoints de `/executions` (API-07)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Dominio alinhado com o CHECK `ck_executions_trigger` da migration
# `0004_executions`. Default "manual" por ser o unico disparavel via API
# hoje (schedule/reprocess virao em CORE-06/API-11).
ExecutionTrigger = Literal["manual", "schedule", "api", "reprocess"]

ExecutionStatus = Literal[
    "queued", "running", "succeeded", "failed", "cancelled", "partial"
]


class CreateExecutionsIn(BaseModel):
    """Payload do POST /executions.

    - `company_ids`: lista nao vazia, unica, de UUIDs. Cada UUID gera
      uma linha em `executions` + um job na fila.
    - `period_start` <= `period_end` (CHECK de dominio defende novamente
      no banco).
    - `dry_run`: nao persiste no schema; vai no `meta` do job RQ e e
      consumido pelo worker (API-13).
    - `trigger`: default `manual`.
    """

    model_config = ConfigDict(extra="forbid")

    company_ids: list[UUID] = Field(min_length=1, max_length=500)
    period_start: date
    period_end: date
    dry_run: bool = False
    trigger: ExecutionTrigger = "manual"

    @field_validator("company_ids")
    @classmethod
    def _dedup(cls, value: list[UUID]) -> list[UUID]:
        seen: set[UUID] = set()
        unique: list[UUID] = []
        for cid in value:
            if cid in seen:
                continue
            seen.add(cid)
            unique.append(cid)
        if not unique:
            raise ValueError("company_ids vazio apos deduplicacao")
        return unique

    @model_validator(mode="after")
    def _check_period(self) -> "CreateExecutionsIn":
        if self.period_end < self.period_start:
            raise ValueError("period_end deve ser >= period_start")
        return self


class CreatedExecution(BaseModel):
    """Item da resposta de POST /executions — uma linha por company."""

    execution_id: UUID
    company_id: UUID
    status: ExecutionStatus
    job_id: Optional[str] = Field(
        default=None,
        description="Id do job no RQ. Null se o enqueue falhou (status=failed).",
    )
    enqueue_error: Optional[str] = Field(
        default=None,
        description="Mensagem curta quando o enqueue falhou apos o INSERT.",
    )


class CreateExecutionsOut(BaseModel):
    """Envelope de POST /executions."""

    created: list[CreatedExecution]


class ExecutionOut(BaseModel):
    """Representacao retornada por GET /executions/{id}."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    company_id: UUID
    trigger: ExecutionTrigger
    status: ExecutionStatus
    period_start: date
    period_end: date
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    nsu_from: Optional[int] = None
    nsu_to: Optional[int] = None
    items_total: int
    items_ok: int
    items_fail: int
    error_summary: Optional[str] = None
    triggered_by_user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
