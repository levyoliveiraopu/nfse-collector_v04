# Auditoria técnica — 2026-04-22

## Escopo

Análise aprofundada dos componentes:

- `apps/api` (FastAPI + auth + RLS + enfileiramento)
- `apps/worker` (consumer RQ + scheduler)
- `packages/worker-core` (motor de execução/coleta)
- `.github/workflows` (qualidade e confiabilidade de entrega)

---

## Problemas **críticos** e correções concretas por arquivo

### 1) Revogação em cadeia de refresh token possivelmente incorreta

**Severidade:** crítica (segurança de sessão).

- **Onde:** `apps/api/api/security/tokens.py` (`_revoke_chain`).
- **Problema técnico:** a CTE recursiva está orientada por `rt.replaced_by = c.id`. No fluxo de rotação implementado no mesmo arquivo, o token antigo recebe `replaced_by = new_id`; portanto, para caminhar para os descendentes, a recursão precisa seguir `c.replaced_by` (ou equivalente). Do jeito atual, a cadeia derivada pode não ser revogada integralmente em detecção de reuse.
- **Impacto prático:** janela de sessão indevida após replay de refresh revogado.

**Correção proposta (arquivo a arquivo):**

1. **`apps/api/api/security/tokens.py`**
   - Reescrever `_revoke_chain` para percorrer descendentes corretamente.
   - Exemplo seguro:

     ```sql
     WITH RECURSIVE chain AS (
       SELECT id, replaced_by
         FROM refresh_tokens
        WHERE id = :rid
       UNION ALL
       SELECT rt.id, rt.replaced_by
         FROM refresh_tokens rt
         JOIN chain c ON rt.id = c.replaced_by
     )
     UPDATE refresh_tokens
        SET revoked_at = COALESCE(revoked_at, now())
      WHERE id IN (SELECT id FROM chain);
     ```

2. **`apps/api/tests/test_auth_tokens_unit.py`**
   - Adicionar cenário de cadeia A→B→C e validar que replay de A revoga B e C.
   - Adicionar cenário de idempotência da revogação (duas execuções sem efeito colateral adicional).

3. **`apps/api/tests/test_auth_routes_integration.py`**
   - Adicionar fluxo e2e: login → refresh (gera B) → refresh (gera C) → reuse de A deve invalidar cadeia inteira.

---

### 2) Condição de corrida no scheduler pode gerar execuções duplicadas

**Severidade:** crítica (integridade operacional + custo + duplicidade de processamento).

- **Onde:** `apps/worker/worker/scheduler.py` (`_has_inflight_execution` + `_insert_execution` no mesmo tick, mas sem lock de concorrência).
- **Problema técnico:** dois schedulers simultâneos podem passar no check de inflight e inserir duas execuções para a mesma company.
- **Impacto prático:** processamento duplicado, carga extra no portal e ruído de ocorrências.

**Correção proposta (arquivo a arquivo):**

1. **`apps/worker/worker/scheduler.py`**
   - Antes do check/insert por `(tenant_id, company_id)`, adquirir lock transacional:

     ```sql
     SELECT pg_advisory_xact_lock(hashtext(:tenant_company_key));
     ```

   - A chave pode ser `f"{tenant_id}:{company_id}"`.
   - Executar lock + check + insert na **mesma transação** (`get_tenant_session`).

2. **`apps/api/alembic/versions/<nova_migration>.py`**
   - (Opcional forte) criar proteção adicional em banco, por exemplo índice parcial em `executions` para status abertos.
   - Exemplo:

     ```sql
     CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ux_exec_open_per_company
       ON executions (tenant_id, company_id)
       WHERE status IN ('queued', 'running');
     ```

3. **`apps/worker/tests/test_scheduler.py`**
   - Adicionar teste de concorrência (dois ticks simultâneos) garantindo apenas uma execução aberta por company.

---

### 3) Pipeline CI não valida todo o núcleo crítico do monorepo

**Severidade:** crítica (risco de regressão indo para `main`).

- **Onde:** `.github/workflows/ci.yml`.
- **Problema técnico:** job `test-python` executa apenas `pytest tests/ -v` (raiz), deixando de fora explicitamente suites de `apps/api/tests` e `apps/worker/tests`.
- **Impacto prático:** mudanças críticas em auth, migrations, scheduler e rotas podem quebrar sem bloquear merge.

**Correção proposta (arquivo a arquivo):**

1. **`.github/workflows/ci.yml`**
   - Alterar etapa de testes Python para:

     ```bash
     pytest tests/ apps/api/tests apps/worker/tests -v
     ```

   - Separar por jobs (api/worker/core) para paralelizar e facilitar troubleshooting.

2. **`apps/api/pyproject.toml` e `apps/worker/pyproject.toml`**
   - (Opcional recomendado) incluir extras de teste mais explícitos e uniformes com `pytest-cov`.

3. **`pytest.ini` (raiz)**
   - Padronizar `testpaths` e marcadores para evitar falsa sensação de cobertura.

---

### 4) Ambiguidade de tenant no login para usuário multi-tenant

**Severidade:** crítica de produto/autorização contextual (pode virar incidente de acesso indevido de contexto).

- **Onde:** `apps/api/api/auth/routes.py` (query de login com `ORDER BY ... LIMIT 1`).
- **Problema técnico:** para usuário membro de múltiplos tenants, o tenant escolhido é implícito/heurístico.
- **Impacto prático:** sessão aberta no tenant “errado”, ações operacionais no contexto indevido.

**Correção proposta (arquivo a arquivo):**

1. **`apps/api/api/auth/schemas.py`**
   - Evoluir `LoginIn` com `tenant_slug` opcional (fase 1) e obrigatório quando houver mais de um vínculo.

2. **`apps/api/api/auth/routes.py`**
   - No login:
     - buscar todas memberships ativas do usuário;
     - se vier 1, segue;
     - se vier >1 e não houver `tenant_slug`, retornar 409/422 orientando seleção;
     - se `tenant_slug` informado, validar associação e usar tenant explícito.

3. **`apps/web-app/app/(auth)/login/page.tsx`**
   - Introduzir etapa de seleção de tenant (ou campo slug temporário) para contas com múltiplas memberships.

4. **`apps/api/tests/test_auth_routes_integration.py`**
   - Adicionar casos de usuário com 2 tenants (com e sem `tenant_slug`).

---

## Ordem recomendada de implementação (curto prazo)

1. `tokens.py` + testes de cadeia (segurança).
2. `scheduler.py` + lock transacional + testes de concorrência.
3. `ci.yml` ampliando cobertura obrigatória.
4. login multi-tenant explícito (contrato de API + UI).

---

## Observação final

Os quatro itens acima são os únicos que eu trataria como “bloqueadores de robustez” para produção imediata. O restante do sistema está em patamar razoável, mas depende dessas correções para reduzir risco real em segurança, confiabilidade e operação.
