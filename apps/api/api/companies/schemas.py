"""Schemas Pydantic do CRUD de `/companies` (API-05)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .cnpj import is_valid_cnpj, normalize_cnpj

CompanyStatus = Literal["active", "paused", "disabled"]

# UF brasileira — dominio fixo de 27 siglas.
_UFS: frozenset[str] = frozenset(
    {
        "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA",
        "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
        "RO", "RR", "RS", "SC", "SE", "SP", "TO",
    }
)


def _normalize_uf(v: str) -> str:
    if not isinstance(v, str):
        raise ValueError("uf deve ser string")
    uf = v.strip().upper()
    if uf not in _UFS:
        raise ValueError(f"uf invalida: {v!r}")
    return uf


def _normalize_cnpj_field(v: str) -> str:
    digits = normalize_cnpj(v)
    if len(digits) != 14:
        raise ValueError("CNPJ deve ter 14 digitos")
    if not is_valid_cnpj(digits):
        raise ValueError("CNPJ invalido (digito verificador nao confere)")
    return digits


class CompanyIn(BaseModel):
    """Payload de criacao (POST /companies)."""

    cnpj: str = Field(description="CNPJ do estabelecimento (com ou sem formatacao).")
    razao_social: str = Field(min_length=2, max_length=200)
    nome_fantasia: Optional[str] = Field(default=None, max_length=200)
    municipio_ibge: str = Field(
        min_length=1,
        max_length=10,
        description="Codigo IBGE do municipio (string para preservar zeros a esquerda).",
    )
    uf: str = Field(min_length=2, max_length=2)
    status: CompanyStatus = Field(default="active")
    portal_provider: Optional[str] = Field(default=None, max_length=60)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("cnpj")
    @classmethod
    def _v_cnpj(cls, v: str) -> str:
        return _normalize_cnpj_field(v)

    @field_validator("uf")
    @classmethod
    def _v_uf(cls, v: str) -> str:
        return _normalize_uf(v)


class CompanyUpdate(BaseModel):
    """Payload de edicao (PATCH /companies/{id}).

    CNPJ e imutavel — para mudar, crie outra company. Todos os demais
    campos sao opcionais; somente os presentes no payload sao aplicados.
    `extra="forbid"` rejeita payloads com `cnpj` (ou qualquer campo
    desconhecido) para proteger contra typos silenciosos.
    """

    model_config = ConfigDict(extra="forbid")

    razao_social: Optional[str] = Field(default=None, min_length=2, max_length=200)
    nome_fantasia: Optional[str] = Field(default=None, max_length=200)
    municipio_ibge: Optional[str] = Field(default=None, min_length=1, max_length=10)
    uf: Optional[str] = Field(default=None, min_length=2, max_length=2)
    status: Optional[CompanyStatus] = Field(default=None)
    portal_provider: Optional[str] = Field(default=None, max_length=60)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("uf")
    @classmethod
    def _v_uf(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _normalize_uf(v)


class CompanyOut(BaseModel):
    """Representacao retornada pelo CRUD."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    cnpj: str
    razao_social: str
    nome_fantasia: Optional[str] = None
    municipio_ibge: str
    uf: str
    status: CompanyStatus
    last_nsu: Optional[int] = None
    last_success_at: Optional[datetime] = None
    portal_provider: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CompanyListOut(BaseModel):
    """Envelope paginado de GET /companies."""

    items: list[CompanyOut]
    page: int
    page_size: int
    total: int
