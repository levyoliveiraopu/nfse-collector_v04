"""Schemas Pydantic do inbox de `/occurrences` (API-09).

Schema da tabela em `apps/api/alembic/versions/0006_occurrences.py`
(DATA-04). Os literais aqui espelham os CHECKs `ck_occurrences_severity`
e `ck_occurrences_status` — manter em sincronia ao expandir.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

OccurrenceSeverity = Literal["info", "warning", "error", "critical"]
OccurrenceStatus = Literal["open", "ack", "snoozed", "resolved", "ignored"]


class OccurrenceOut(BaseModel):
    """Representacao retornada pelos endpoints de leitura."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    company_id: UUID
    execution_id: Optional[UUID] = None
    severity: OccurrenceSeverity
    code: str
    title: str
    detail: Optional[str] = None
    status: OccurrenceStatus
    assignee_user_id: Optional[UUID] = None
    first_seen_at: datetime
    last_seen_at: datetime
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class OccurrenceListOut(BaseModel):
    """Envelope paginado de GET /occurrences."""

    items: list[OccurrenceOut]
    page: int
    page_size: int
    total: int


class OccurrenceResolveIn(BaseModel):
    """Body de POST /occurrences/{id}/resolve.

    A nota e obrigatoria pelo ticket — registrada em
    `audit_logs.metadata.note` (a tabela `occurrences` nao tem coluna
    dedicada nesta entrega; auditoria preserva o historico).
    """

    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=1, max_length=2000)


class OccurrenceAssignIn(BaseModel):
    """Body de POST /occurrences/{id}/assign."""

    model_config = ConfigDict(extra="forbid")

    assignee_user_id: UUID
