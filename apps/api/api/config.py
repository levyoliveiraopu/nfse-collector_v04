"""Configuracao da API carregada via variaveis de ambiente (pydantic-settings).

Convencoes:
- Todas as variaveis usam prefixo `API_` (ex: `API_LOG_LEVEL`).
- `.env` na raiz do repo e carregado automaticamente se existir.
- Nenhum segredo tem default: campos opcionais recebem `""` ou `None`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from . import __version__


class Settings(BaseSettings):
    """Configuracao runtime da API."""

    model_config = SettingsConfigDict(
        env_prefix="API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="nfse-api")
    environment: Literal["development", "staging", "production"] = Field(
        default="development"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    version: str = Field(default=__version__)
    git_commit: str = Field(default="unknown")

    # Conexao Postgres usada pela API e por Alembic (DATA-01).
    # Formato recomendado: "postgresql+psycopg://user:pass@host:5432/dbname".
    # Vazio por default para nao quebrar ambientes que ainda nao usam DB.
    database_url: str = Field(default="")

    # -----------------------------------------------------------------
    # Auth (API-02)
    # -----------------------------------------------------------------
    # Segredo HS256 do JWT. Obrigatorio em staging/production (validado
    # abaixo). Em development pode ficar vazio — o sistema cai para um
    # fallback de dev que emite um warning alto.
    jwt_secret: str = Field(default="")
    jwt_issuer: str = Field(default="nfse-api")
    jwt_audience: str = Field(default="nfse-web")

    access_token_ttl_minutes: int = Field(default=15, ge=1, le=60 * 24)
    refresh_token_ttl_days: int = Field(default=7, ge=1, le=90)

    # Formato aceito pelo slowapi: "<count>/<period>" (ex: "5/minute").
    login_rate_limit: str = Field(default="5/minute")

    @model_validator(mode="after")
    def _validate_auth_secrets(self) -> "Settings":
        if self.environment in ("staging", "production") and not self.jwt_secret:
            raise ValueError(
                "API_JWT_SECRET e obrigatorio em staging/production. "
                "Defina a variavel de ambiente antes de subir a API."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna singleton de Settings (cache por processo)."""
    return Settings()
