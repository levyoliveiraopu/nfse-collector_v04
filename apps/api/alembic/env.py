"""Ambiente Alembic da API (DATA-01).

Resolve a URL de conexao a partir de `API_DATABASE_URL` via `Settings`
(pydantic-settings). Nao usa autogenerate: as migrations sao escritas
a mao para ter controle explicito sobre DDL (RLS, roles, policies).
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from api.config import get_settings

# Configuracao lida do alembic.ini.
config = context.config

# Logging declarado no alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic autogenerate nao sera usado nesta fase (migrations manuais).
target_metadata = None


def _resolve_database_url() -> str:
    """Resolve a URL do Postgres a partir de Settings ou env direto.

    Ordem de precedencia:
    1. `-x url=...` passado na CLI do Alembic (uso pontual em testes).
    2. `API_MIGRATION_DATABASE_URL` direto (role admin/migrator).
    3. `API_DATABASE_URL` via pydantic-settings.
    4. `DATABASE_URL` cru (fallback conveniente).
    """
    x_args = context.get_x_argument(as_dictionary=True)
    if x_args.get("url"):
        return x_args["url"]

    migration_url = os.getenv("API_MIGRATION_DATABASE_URL", "")
    if migration_url:
        return migration_url

    settings = get_settings()
    if settings.database_url:
        return settings.database_url

    raw = os.getenv("DATABASE_URL", "")
    if raw:
        return raw

    raise RuntimeError(
        "API_DATABASE_URL nao definida. Exporte a variavel ou passe -x url=postgresql+psycopg://... para o Alembic."
    )


def run_migrations_offline() -> None:
    """Roda migrations em modo offline (emite SQL sem abrir conexao)."""
    url = _resolve_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Roda migrations conectando ao banco real."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _resolve_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
