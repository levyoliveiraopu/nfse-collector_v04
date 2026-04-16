"""Schemas Pydantic do CRUD de `/schedules` (API-12)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .cron import CronValidationError, validate_cron, validate_timezone


def _check_cron(v: str) -> str:
    try:
        return validate_cron(v)
    except CronValidationError as exc:
        # Pydantic -> HTTP 422; o handler POST re-valida e retorna 400
        # para o contrato "cron invalido -> 400 claro" do DoD (via
        # catch no router antes do insert). Aqui preservamos a mensagem
        # para o caso em que o cron venha via PATCH.
        raise ValueError(str(exc)) from exc


def _check_tz(v: str) -> str:
    try:
        return validate_timezone(v)
    except CronValidationError as exc:
        raise ValueError(str(exc)) from exc


class ScheduleIn(BaseModel):
    """Payload de criacao (POST /schedules)."""

    model_config = ConfigDict(extra="forbid")

    cron_expr: str = Field(description="Expressao cron 5 campos (ex.: '0 3 * * *').")
    timezone: str = Field(
        default="America/Sao_Paulo",
        description="Nome IANA (ex.: 'America/Sao_Paulo').",
    )
    company_id: Optional[UUID] = Field(
        default=None,
        description="Company alvo. Null = agenda valida para o tenant inteiro.",
    )
    enabled: bool = Field(default=True)

    @field_validator("cron_expr")
    @classmethod
    def _v_cron(cls, v: str) -> str:
        return _check_cron(v)

    @field_validator("timezone")
    @classmethod
    def _v_tz(cls, v: str) -> str:
        return _check_tz(v)


class ScheduleUpdate(BaseModel):
    """Payload de edicao (PATCH /schedules/{id}).

    `extra="forbid"` impede o cliente de tocar campos read-only como
    `last_run_at`, `next_run_at`, `tenant_id`, `created_by_user_id`.
    Para pausar/resumir use `enabled`.
    """

    model_config = ConfigDict(extra="forbid")

    cron_expr: Optional[str] = Field(default=None)
    timezone: Optional[str] = Field(default=None)
    company_id: Optional[UUID] = Field(default=None)
    enabled: Optional[bool] = Field(default=None)

    @field_validator("cron_expr")
    @classmethod
    def _v_cron(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _check_cron(v)

    @field_validator("timezone")
    @classmethod
    def _v_tz(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _check_tz(v)


class ScheduleOut(BaseModel):
    """Representacao retornada pelo CRUD."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    company_id: Optional[UUID] = None
    cron_expr: str
    timezone: str
    enabled: bool
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_by_user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class ScheduleListOut(BaseModel):
    """Envelope paginado de GET /schedules."""

    items: list[ScheduleOut]
    page: int
    page_size: int
    total: int


class SchedulePresetOut(BaseModel):
    """Sugestao de cron pronta para a UI (GET /schedules/presets)."""

    id: str
    label: str
    cron_expr: str
    description: str


class SchedulePresetListOut(BaseModel):
    items: list[SchedulePresetOut]
