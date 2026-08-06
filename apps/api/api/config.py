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
    environment: Literal["development", "staging", "production"] = Field(default="development")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
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

    # -----------------------------------------------------------------
    # Credenciais PFX (API-06)
    # -----------------------------------------------------------------
    # KEK (Key Encryption Key) AES-256 codificada em Base64 url-safe
    # (32 bytes -> 43 chars sem padding ou 44 com `=`). Obrigatoria
    # em staging/production. Em development cai para uma KEK derivada
    # deterministicamente (NUNCA usar fora de dev).
    credential_kek_b64: str = Field(default="")
    # Teto do upload de PFX (defesa contra abuso de multipart).
    # PFX A1 tipico tem ~5 KB; 1 MiB e folga generosa.
    credential_max_pfx_bytes: int = Field(default=1_048_576, ge=1024, le=10 * 1024 * 1024)

    # -----------------------------------------------------------------
    # Storage S3 (INFRA-06)
    # -----------------------------------------------------------------
    # Lidos do mesmo bloco S3_* do .env (sem prefixo API_) — herdamos via
    # alias para nao duplicar o que ja existe em config/.env.example.
    s3_endpoint: str = Field(default="", validation_alias="S3_ENDPOINT")
    s3_region: str = Field(default="us-east-1", validation_alias="S3_REGION")
    s3_bucket: str = Field(default="", validation_alias="S3_BUCKET")
    s3_key_id: str = Field(default="", validation_alias="S3_KEY_ID")
    s3_application_key: str = Field(default="", validation_alias="S3_APPLICATION_KEY")
    s3_force_path_style: bool = Field(default=True, validation_alias="S3_FORCE_PATH_STYLE")
    # Prefix dedicado para PFX cifrados (sem lifecycle — credencial e viva).
    # Owner deve criar bucket sem regra para este prefix; ver infra/s3-bucket.md.
    s3_credentials_prefix: str = Field(
        default="tenants-credentials/",
        validation_alias="S3_CREDENTIALS_PREFIX",
    )

    # -----------------------------------------------------------------
    # Fila Redis (API-07)
    # -----------------------------------------------------------------
    # URL do Redis usado para enfileirar jobs do worker (RQ). Formato:
    # "redis://[:password@]host:port/db". Vazio em development permite
    # rodar a API sem fila; `POST /executions` so exige Redis online
    # no momento do disparo e devolve 502 em indisponibilidade.
    redis_url: str = Field(default="", validation_alias="API_REDIS_URL")
    # Nome da fila RQ consumida pelo worker (CORE-05 / API-13).
    queue_name: str = Field(
        default="nfse-executions",
        validation_alias="API_QUEUE_NAME",
    )
    job_timeout_seconds: int = Field(
        default=60 * 60,
        ge=60,
        le=24 * 60 * 60,
        validation_alias="API_JOB_TIMEOUT_SECONDS",
    )

    # -----------------------------------------------------------------
    # CORS
    # -----------------------------------------------------------------
    # Origens permitidas para chamadas cross-origin do browser (painel).
    # Lista separada por virgula (ex: "https://app.exemplo.com").
    # Vazio (default) = CORS desligado; use quando o painel e a API
    # compartilham a mesma origem (ex: painel em / e API em /backend).
    cors_origins: str = Field(default="", validation_alias="API_CORS_ORIGINS")

    @property
    def cors_origins_list(self) -> list[str]:
        """Origens CORS parseadas da string separada por virgula."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _validate_auth_secrets(self) -> "Settings":
        if self.environment in ("staging", "production") and not self.jwt_secret:
            raise ValueError(
                "API_JWT_SECRET e obrigatorio em staging/production. "
                "Defina a variavel de ambiente antes de subir a API."
            )
        if (
            self.environment in ("staging", "production")
            and len(self.jwt_secret.encode("utf-8")) < 32
        ):
            raise ValueError(
                "API_JWT_SECRET deve ter pelo menos 32 bytes em "
                "staging/production (HS256). Gere com: openssl rand -base64 32"
            )
        if self.environment in ("staging", "production") and not self.credential_kek_b64:
            raise ValueError(
                "API_CREDENTIAL_KEK_B64 e obrigatorio em staging/production. "
                "Gere com: python -c 'import secrets,base64; "
                "print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna singleton de Settings (cache por processo)."""
    return Settings()
