"""Schemas Pydantic do upload/revogacao de credencial PFX (API-06)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

CredentialStatus = Literal["active", "expired", "revoked", "invalid"]


class CredentialOut(BaseModel):
    """Resposta retornada pelo POST/DELETE de credencial.

    Nunca contem ciphertext nem fingerprint da chave privada — apenas
    metadados publicos do certificado X.509.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    company_id: UUID
    type: Literal["pfx_a1"] = "pfx_a1"
    pfx_object_key: str
    cert_fingerprint: Optional[str] = None
    cert_not_before: Optional[datetime] = None
    cert_not_after: Optional[datetime] = None
    status: CredentialStatus
    cn_matches_cnpj: bool
    created_at: datetime
    updated_at: datetime
