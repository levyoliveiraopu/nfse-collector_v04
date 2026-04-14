"""Fixtures compartilhadas dos testes de `apps/api`.

O principal consumidor e `test_rls_isolation.py` (DATA-06), que precisa
de dois tenants semeados e de uma forma de abrir sessoes como a role
`app_user` (NOBYPASSRLS) com `SET LOCAL app.current_tenant` ou sem GUC
nenhuma (cenario fail-closed).

Todas as fixtures sao gated por `TEST_DATABASE_URL`: sem a variavel, os
testes de integracao sao pulados, mantendo o `pytest` rapido em maquinas
de dev que nao tenham Postgres rodando.
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator

import pytest

try:  # psycopg so e necessario para os testes de integracao.
    import psycopg
except ImportError:  # pragma: no cover - defensivo em dev minimo
    psycopg = None  # type: ignore[assignment]


# Lista canonica de tabelas protegidas por Row Level Security no schema
# atual (DATA-01 ... DATA-05 + API-02). `tenants` usa a coluna `id` (nao
# `tenant_id`) no predicado da policy; por isso e tratada separadamente
# nos testes parametrizados.
RLS_TABLES: tuple[str, ...] = (
    "tenants",
    "tenant_users",
    "companies",
    "company_credentials",
    "executions",
    "execution_items",
    "occurrences",
    "reprocess_jobs",
    "notifications",
    "refresh_tokens",
    "files",
    "schedules",
    "audit_logs",
    "subscriptions",
)

# Tabelas cuja policy filtra por `tenant_id = GUC`. Excluem `tenants`
# (policy usa `id = GUC`) mas sao exercitadas do mesmo jeito.
RLS_TABLES_WITH_TENANT_ID: tuple[str, ...] = tuple(
    t for t in RLS_TABLES if t != "tenants"
)

TRUNCATE_SQL = (
    "TRUNCATE "
    "subscriptions, audit_logs, schedules, files, "
    "refresh_tokens, notifications, reprocess_jobs, "
    "occurrences, execution_items, executions, "
    "company_credentials, companies, tenant_users, "
    "users, tenants "
    "RESTART IDENTITY CASCADE"
)


@dataclass(frozen=True)
class TenantSeed:
    """Identificadores das linhas semeadas para um tenant."""

    id: uuid.UUID
    slug: str
    user_id: uuid.UUID
    company_id: uuid.UUID
    credential_id: uuid.UUID
    execution_id: uuid.UUID
    execution_item_id: uuid.UUID
    occurrence_id: uuid.UUID
    reprocess_job_id: uuid.UUID
    notification_id: uuid.UUID
    refresh_token_id: uuid.UUID
    file_id: uuid.UUID
    schedule_id: uuid.UUID
    audit_log_id: int
    subscription_id: uuid.UUID


def _normalize_dsn(url: str) -> str:
    """Converte uma URL no formato SQLAlchemy (`postgresql+psycopg://`)
    para o formato que `psycopg.connect` entende (`postgresql://`)."""
    return url.replace("postgresql+psycopg://", "postgresql://")


@pytest.fixture(scope="session")
def rls_db_url() -> str:
    dsn = os.getenv("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip(
            "TEST_DATABASE_URL nao definida — pulando testes de integracao RLS."
        )
    if psycopg is None:  # pragma: no cover
        pytest.skip("psycopg nao instalado — pulando testes de integracao RLS.")
    return _normalize_dsn(dsn)


def _seed_tenant(conn, *, slug: str, email: str) -> TenantSeed:
    """Cria 1 tenant + 1 user + 1 linha em cada tabela RLS.

    Roda como role superuser (BYPASSRLS implicito) e por isso consegue
    inserir em varios tenants na mesma conexao. Usa `ON CONFLICT` em
    `plans` para tolerar execucoes repetidas contra o mesmo banco.
    """
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO plans (code, name, price_cents) "
        "VALUES ('rls-test', 'RLS test plan', 0) "
        "ON CONFLICT (code) DO NOTHING"
    )

    cur.execute(
        "INSERT INTO tenants (name, slug, plan_id) "
        "VALUES (%s, %s, 'rls-test') RETURNING id",
        (slug.title(), slug),
    )
    tenant_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO users (email, name) VALUES (%s, %s) RETURNING id",
        (email, email.split("@")[0]),
    )
    user_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO tenant_users (tenant_id, user_id, role) "
        "VALUES (%s, %s, 'owner')",
        (tenant_id, user_id),
    )

    cur.execute(
        "INSERT INTO companies "
        "(tenant_id, cnpj, razao_social, municipio_ibge, uf) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (tenant_id, "00000000000191", f"{slug.title()} LTDA", "3550308", "SP"),
    )
    company_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO company_credentials "
        "(tenant_id, company_id, pfx_object_key, pfx_password_ciphertext) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (tenant_id, company_id, f"tenants/{slug}/cert.pfx", b"\x00\x01\x02"),
    )
    credential_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO executions "
        "(tenant_id, company_id, trigger, period_start, period_end, "
        " status, started_at) "
        "VALUES (%s, %s, 'manual', '2026-03-01', '2026-03-31', "
        "        'running', now()) RETURNING id",
        (tenant_id, company_id),
    )
    execution_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO execution_items "
        "(execution_id, tenant_id, nsu, chave_nfse, status) "
        "VALUES (%s, %s, 1001, %s, 'ok') RETURNING id",
        (execution_id, tenant_id, f"chave-{slug}-0001"),
    )
    execution_item_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO occurrences "
        "(tenant_id, company_id, severity, code, title) "
        "VALUES (%s, %s, 'warning', 'TEST', 'Ocorrencia seed') "
        "RETURNING id",
        (tenant_id, company_id),
    )
    occurrence_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO reprocess_jobs (tenant_id) VALUES (%s) RETURNING id",
        (tenant_id,),
    )
    reprocess_job_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO notifications (tenant_id, channel, type) "
        "VALUES (%s, 'inapp', 'test') RETURNING id",
        (tenant_id,),
    )
    notification_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO refresh_tokens "
        "(tenant_id, user_id, token_hash, expires_at) "
        "VALUES (%s, %s, %s, now() + interval '7 days') RETURNING id",
        (tenant_id, user_id, f"hash-{slug}"),
    )
    refresh_token_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO files "
        "(tenant_id, kind, object_key, bytes, checksum_sha256) "
        "VALUES (%s, 'other', %s, 10, %s) RETURNING id",
        (tenant_id, f"tenants/{slug}/obj.bin", "a" * 64),
    )
    file_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO schedules (tenant_id, company_id, cron_expr) "
        "VALUES (%s, %s, '0 3 * * *') RETURNING id",
        (tenant_id, company_id),
    )
    schedule_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO audit_logs (tenant_id, action, resource_type) "
        "VALUES (%s, 'seed', 'tenant') RETURNING id",
        (tenant_id,),
    )
    audit_log_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO subscriptions (tenant_id, plan_id, status) "
        "VALUES (%s, 'rls-test', 'trialing') RETURNING id",
        (tenant_id,),
    )
    subscription_id = cur.fetchone()[0]

    cur.close()

    return TenantSeed(
        id=tenant_id,
        slug=slug,
        user_id=user_id,
        company_id=company_id,
        credential_id=credential_id,
        execution_id=execution_id,
        execution_item_id=execution_item_id,
        occurrence_id=occurrence_id,
        reprocess_job_id=reprocess_job_id,
        notification_id=notification_id,
        refresh_token_id=refresh_token_id,
        file_id=file_id,
        schedule_id=schedule_id,
        audit_log_id=audit_log_id,
        subscription_id=subscription_id,
    )


@pytest.fixture(scope="module")
def rls_seed(rls_db_url: str) -> Iterator[dict[str, TenantSeed]]:
    """Semeia dois tenants (A e B) com linhas em todas as tabelas RLS.

    Roda como superuser (BYPASSRLS) e por isso conviver com a RLS ativa
    e as policies `FORCE ROW LEVEL SECURITY`. Truncate explicito antes
    e depois garante que o banco fica limpo para outras suites.
    """
    assert psycopg is not None  # garantido por rls_db_url
    with psycopg.connect(rls_db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(TRUNCATE_SQL)

        seeds = {
            "A": _seed_tenant(conn, slug="rls-a", email="a@rls.test"),
            "B": _seed_tenant(conn, slug="rls-b", email="b@rls.test"),
        }

    yield seeds

    with psycopg.connect(rls_db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(TRUNCATE_SQL)
            cur.execute("DELETE FROM plans WHERE code = 'rls-test'")


@pytest.fixture()
def app_user_cursor(rls_db_url: str) -> Callable:
    """Devolve um context manager que abre conexao nova e troca a role
    para `app_user` (`NOBYPASSRLS`) dentro de uma transacao.

    Uso:

        with app_user_cursor(tenant_id=uuid_a) as cur:
            cur.execute(...)

        # Sem tenant_id -> sem SET LOCAL app.current_tenant (fail-closed).
        with app_user_cursor() as cur:
            cur.execute(...)

    A transacao sempre e revertida ao final para nao poluir o banco.
    """
    assert psycopg is not None  # garantido por rls_db_url

    @contextmanager
    def _scope(tenant_id: uuid.UUID | str | None = None):
        with psycopg.connect(rls_db_url) as conn:
            # autocommit=False: psycopg abre transacao implicita no
            # primeiro statement, habilitando SET LOCAL.
            with conn.cursor() as cur:
                cur.execute("SET LOCAL ROLE app_user")
                if tenant_id is not None:
                    # `SET LOCAL` do Postgres nao aceita parametros
                    # preparados ($1); usamos `set_config(name, value,
                    # is_local=true)` como equivalente funcional.
                    cur.execute(
                        "SELECT set_config('app.current_tenant', %s, true)",
                        (str(tenant_id),),
                    )
                try:
                    yield cur
                finally:
                    conn.rollback()

    return _scope
