"""Schemas Pydantic dos endpoints de autenticacao (API-02)."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class SignupIn(BaseModel):
    """Cria um tenant novo e um usuario owner em uma unica chamada."""

    tenant_name: str = Field(min_length=2, max_length=120)
    tenant_slug: str = Field(
        min_length=2,
        max_length=60,
        pattern=r"^[a-z0-9][a-z0-9-]{0,58}[a-z0-9]$",
        description="Slug unico do tenant (ex: 'acme-contabil').",
    )
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=512)


class LogoutIn(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=512)


class AuthOut(BaseModel):
    """Par access + refresh devolvido em signup/login/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    tenant_id: str
    user_id: str
    role: str


class LogoutOut(BaseModel):
    revoked: bool
