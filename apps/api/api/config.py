"""Configuracao da API carregada via variaveis de ambiente (pydantic-settings).

Convencoes:
- Todas as variaveis usam prefixo `API_` (ex: `API_LOG_LEVEL`).
- `.env` na raiz do repo e carregado automaticamente se existir.
- Nenhum segredo tem default: campos opcionais recebem `""` ou `None`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna singleton de Settings (cache por processo)."""
    return Settings()
