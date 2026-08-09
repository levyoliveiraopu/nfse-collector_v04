"""Schemas Pydantic dos endpoints de autenticacao (API-02)."""

from __future__ import annotations

from typing import Annotated

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    ValidatorFunctionWrapHandler,
    WrapValidator,
)

from api.config import get_settings


def _validate_login_email(value: object, handler: ValidatorFunctionWrapHandler) -> str:
    """Aceita a identidade reservada somente na stack local explicita."""

    settings = get_settings()
    if (
        settings.environment == "development"
        and settings.allow_local_demo_login
        and isinstance(value, str)
        and value.lower() == "admin@demo.local"
    ):
        return value.lower()
    return str(handler(value))


LoginEmail = Annotated[EmailStr, WrapValidator(_validate_login_email)]


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
    email: LoginEmail
    password: str = Field(min_length=1, max_length=256)
    tenant_slug: str | None = Field(
        default=None,
        min_length=2,
        max_length=60,
        pattern=r"^[a-z0-9][a-z0-9-]{0,58}[a-z0-9]$",
        description=(
            "Slug do tenant. Obrigatorio quando o usuario tem mais de "
            "uma membership ativa."
        ),
    )


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


class MeOut(BaseModel):
    """Identidade corrente derivada do JWT (API-03).

    Serve como prova de vida do middleware de tenant: se o handler
    responde, o `SET LOCAL app.current_tenant` foi aplicado e o RLS
    esta ativo nesta request.
    """

    tenant_id: str
    user_id: str
    role: str
    memberships_visible: int
