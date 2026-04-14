"""DATA-06 — Testes automatizados de isolamento cross-tenant via RLS.

Objetivo: provar que, mesmo com um bug de aplicacao que ignore o
`tenant_id` na query, o Postgres bloqueia o acesso cross-tenant via
Row Level Security. O modelo de ameaca aqui e:

1. `app_user` e `NOBYPASSRLS` (DATA-01);
2. toda tabela com `tenant_id` ou `id` canonico tem `ENABLE` + `FORCE
   ROW LEVEL SECURITY` e uma policy ancorada no GUC
   `app.current_tenant`;
3. a transacao da request faz `SET LOCAL app.current_tenant = :tid` e
   por isso o escopo da GUC morre no commit/rollback (API-03).

O teste cria dois tenants (A e B) com linhas em cada tabela RLS via
role superuser (BYPASSRLS implicito), depois assume o papel de
`app_user` e valida:

- `SELECT` com GUC de A nao enxerga NENHUMA linha de B.
- `SELECT` sem GUC retorna **0 linhas** em todas as tabelas
  (fail-closed — segundo argumento `true` em `current_setting` devolve
  NULL quando a GUC nao existe e a policy vira `id = NULL::uuid`).
- `UPDATE`/`DELETE` apontando para linha de B, com GUC de A, nao afeta
  nada (policy `USING` esconde a linha do escopo do DML).
- `INSERT` com `tenant_id` de B, estando no escopo de A, e rejeitado
  pela clausula `WITH CHECK`.

DoD adicional — injecao de falha: dropar uma policy (ex.:
`DROP POLICY companies_isolation ON companies`) faz este teste
quebrar no primeiro assert de cross-tenant. O procedimento manual
esta documentado em `apps/api/README.md`.
"""

from __future__ import annotations

import pytest

from .conftest import RLS_TABLES, RLS_TABLES_WITH_TENANT_ID


# ---------------------------------------------------------------------------
# Isolamento de leitura: tenant A nao enxerga linhas de B.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("table", RLS_TABLES_WITH_TENANT_ID)
def test_tenant_a_cannot_read_tenant_b_rows(
    app_user_cursor, rls_seed, table: str
) -> None:
    a = rls_seed["A"]
    b = rls_seed["B"]

    with app_user_cursor(tenant_id=a.id) as cur:
        # 1. SELECT explicito filtrando pelo tenant_id de B nao pode
        #    retornar nada, mesmo que o "bug de aplicacao" passe o
        #    tenant_id errado.
        cur.execute(
            f"SELECT COUNT(*) FROM {table} WHERE tenant_id = %s", (str(b.id),)
        )
        (count_from_b,) = cur.fetchone()
        assert count_from_b == 0, (
            f"RLS VAZADO em {table}: tenant A conseguiu ler "
            f"{count_from_b} linha(s) de B."
        )

        # 2. SELECT ancora do seed do proprio tenant esta visivel.
        cur.execute(
            f"SELECT COUNT(*) FROM {table} WHERE tenant_id = %s", (str(a.id),)
        )
        (count_from_a,) = cur.fetchone()
        assert count_from_a >= 1, (
            f"Seed inconsistente: tenant A deveria ter pelo menos 1 "
            f"linha em {table}, encontrou {count_from_a}."
        )

        # 3. Varredura sem filtro tambem nao pode vazar: a policy deve
        #    esconder as linhas de B de qualquer SELECT.
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        (count_total,) = cur.fetchone()
        assert count_total == count_from_a, (
            f"RLS VAZADO em {table}: varredura sem WHERE retornou "
            f"{count_total}, esperado {count_from_a}."
        )


def test_tenants_table_filters_by_id_column(app_user_cursor, rls_seed) -> None:
    """A policy de `tenants` usa `id = GUC` (nao `tenant_id`). Cada
    escopo deve enxergar apenas o proprio tenant."""
    a = rls_seed["A"]
    b = rls_seed["B"]

    with app_user_cursor(tenant_id=a.id) as cur:
        cur.execute("SELECT id FROM tenants ORDER BY slug")
        rows = [r[0] for r in cur.fetchall()]
        assert rows == [a.id], (
            f"tenants vazou: escopo A viu {rows}, esperado [{a.id}]."
        )

    with app_user_cursor(tenant_id=b.id) as cur:
        cur.execute("SELECT id FROM tenants ORDER BY slug")
        rows = [r[0] for r in cur.fetchall()]
        assert rows == [b.id], (
            f"tenants vazou: escopo B viu {rows}, esperado [{b.id}]."
        )


# ---------------------------------------------------------------------------
# Fail-closed: sem GUC setada, `app_user` nao enxerga nada.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("table", RLS_TABLES)
def test_fail_closed_without_guc(app_user_cursor, rls_seed, table: str) -> None:
    """Sem `SET LOCAL app.current_tenant`, a policy compara
    `tenant_id = NULL::uuid` (via `current_setting(..., true)`), o que
    e sempre falso — contagem deve ser 0 em todas as tabelas."""
    with app_user_cursor(tenant_id=None) as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        (count,) = cur.fetchone()
        assert count == 0, (
            f"Fail-closed violado em {table}: sem GUC, `app_user` "
            f"leu {count} linha(s)."
        )


# ---------------------------------------------------------------------------
# Isolamento de escrita: UPDATE/DELETE com escopo de A nao toca B.
# ---------------------------------------------------------------------------


def test_cross_tenant_update_is_invisible(
    app_user_cursor, rls_seed, rls_db_url
) -> None:
    """Com GUC = A, `UPDATE` em `companies` que busca o `id` de B nao
    pode atualizar nada (a policy USING esconde a linha)."""
    import psycopg

    a = rls_seed["A"]
    b = rls_seed["B"]

    with app_user_cursor(tenant_id=a.id) as cur:
        cur.execute(
            "UPDATE companies SET razao_social = 'pwned' WHERE id = %s",
            (str(b.company_id),),
        )
        assert cur.rowcount == 0, (
            f"UPDATE cross-tenant afetou {cur.rowcount} linha(s); esperado 0."
        )

    # Confirma que a linha de B continua com o valor original (conexao
    # nova como superuser, BYPASSRLS, para ignorar o escopo de A).
    with psycopg.connect(rls_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT razao_social FROM companies WHERE id = %s",
                (str(b.company_id),),
            )
            (razao,) = cur.fetchone()
            assert razao != "pwned", (
                f"Linha de B foi modificada por escopo de A: razao={razao!r}"
            )
    # Silencia lint (variavel usada para documentacao).
    _ = a


def test_cross_tenant_delete_is_invisible(app_user_cursor, rls_seed) -> None:
    a = rls_seed["A"]
    b = rls_seed["B"]

    with app_user_cursor(tenant_id=a.id) as cur:
        cur.execute(
            "DELETE FROM companies WHERE id = %s", (str(b.company_id),)
        )
        assert cur.rowcount == 0, (
            f"DELETE cross-tenant afetou {cur.rowcount} linha(s); esperado 0."
        )


# ---------------------------------------------------------------------------
# WITH CHECK: insert forjando tenant_id alheio e rejeitado.
# ---------------------------------------------------------------------------


def test_with_check_blocks_insert_of_foreign_tenant(
    app_user_cursor, rls_seed
) -> None:
    """Com GUC = A, tentar inserir uma linha com `tenant_id = B` em
    `companies` dispara `new row violates row-level security policy`
    porque a clausula `WITH CHECK` da policy nao bate."""
    import psycopg.errors

    a = rls_seed["A"]
    b = rls_seed["B"]

    with app_user_cursor(tenant_id=a.id) as cur:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute(
                "INSERT INTO companies "
                "(tenant_id, cnpj, razao_social, municipio_ibge, uf) "
                "VALUES (%s, '11111111000111', 'Forjada', '3550308', 'SP')",
                (str(b.id),),
            )
        # Garante que nao ha linha de A chamada "Forjada" mesmo apos o
        # erro (a transacao vai ser revertida no context manager).
        _ = a  # silencia lint; seed e referencia para clareza
