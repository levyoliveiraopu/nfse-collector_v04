"""Schemas Pydantic de `/files` (API-11)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# Dominio alinhado com o CHECK `ck_files_kind` em 0011_files.py.
FileKind = Literal["nfse_xml", "export", "pfx", "report", "other"]


class FileOut(BaseModel):
    """Linha de `files` devolvida pelo GET /files."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    kind: FileKind
    object_key: str
    bytes: int
    checksum_sha256: str
    source_execution_id: Optional[UUID] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class FileListOut(BaseModel):
    """Envelope paginado."""

    items: list[FileOut]
    page: int
    page_size: int
    total: int


class FileUrlOut(BaseModel):
    """Resposta do GET /files/{id}/url — URL pre-assinada."""

    url: str
    expires_in: int  # segundos ate expirar
    expires_at: datetime  # instante UTC em que a URL deixa de valer
