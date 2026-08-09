"""Schemas Pydantic dos endpoints de `/exports` (API-15)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

# Formatos publicos implementados pelo worker.
ExportKind = Literal["zip_xml", "excel_nfse"]

ExportStatus = Literal["queued", "running", "ready", "failed", "empty"]


class CreateExportIn(BaseModel):
    """Payload do POST /exports.

    - `company_id`: UUID da company (escopo do export). RLS valida
      ownership pelo tenant.
    - `period_start` <= `period_end` (validado aqui e via CHECK no DB).
    - `kind`: ZIP dos XMLs ou planilha das NFS-e emitidas.
    """

    model_config = ConfigDict(extra="forbid")

    company_id: UUID
    period_start: date
    period_end: date
    kind: ExportKind = "zip_xml"

    @model_validator(mode="after")
    def _check_period(self) -> "CreateExportIn":
        if self.period_end < self.period_start:
            raise ValueError("period_end deve ser >= period_start")
        return self


class ExportOut(BaseModel):
    """Representacao de um pedido de export.

    `download_url` + `expires_in` vem preenchidos **somente** quando
    `status == 'ready'` e `file_id` esta populado. Em qualquer outro
    estado ficam como `None`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    company_id: UUID
    requested_by_user_id: Optional[UUID] = None
    kind: ExportKind
    period_start: date
    period_end: date
    status: ExportStatus
    file_id: Optional[UUID] = None
    items_count: int
    total_bytes: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    download_url: Optional[str] = None
    expires_in: Optional[int] = None


class CreateExportOut(BaseModel):
    """Resposta do POST /exports."""

    export_id: UUID
    status: ExportStatus
    job_id: Optional[str] = None
    enqueue_error: Optional[str] = None
