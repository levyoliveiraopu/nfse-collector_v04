# STATE — NFS-e SaaS

> Fonte unica de verdade sobre o estado atual do projeto.
> Toda PR deve atualizar este arquivo antes do merge.

## Decisoes Ativas

| ID | Decisao | Status |
|----|---------|--------|
| ADR-001 | Monolito modular Python (FastAPI) + Next.js | ativo |
| ADR-002 | Multi-tenant single-DB com Row Level Security | ativo |
| ADR-003 | Storage S3 externo, cifra PFX AES-GCM, retencao 90d sem arquivamento | ativo |
| ADR-004 | Billing adiado: schema pronto, integracao depois | ativo |
| ADR-005 | Deploy Docker Compose em VPS Hostinger + Nginx host | ativo |

## Em Andamento

- **2026-08-08 - Compatibilidade com o leiaute nacional v1.01:** o parser
  passa a ler a chave em `infNFSe/@Id`, a descricao em `xDescServ`, o valor
  em `vServPrest/vServ` e a retencao em `tpRetISSQN` com a semantica oficial.
  Identificadores no Excel sao gravados como texto para preservar zeros e
  evitar notacao cientifica. Valores de ISS ausentes no XML permanecem
  vazios, sem estimativa ou fabricacao de dado fiscal.

- **2026-08-08 - RLS do worker em PostgreSQL:** corrigida a abertura da
  sessao tenant do `worker-core` para usar
  `SELECT set_config('app.current_tenant', :tid, true)`. A forma anterior,
  `SET LOCAL ... = :tid`, era convertida pelo psycopg em `$1` e falhava com
  erro de sintaxe antes de qualquer chamada ao ADN. Teste de contrato garante
  o GUC parametrizado e restrito a transacao. O smoke real tambem revelou e
  corrigiu uma colisao de nomes entre os helpers `_mark_running` de execucao e
  export, que impedia os jobs de ZIP/Excel antes da leitura dos XMLs.

- **2026-08-08 - NFS-e emitidas e export fiscal:** a coleta continua
  persistindo todos os documentos distribuidos pelo ADN para manter a
  sequencia NSU, mas os contadores e a listagem padrao agora consideram
  somente o CNPJ da empresa como emitente; `scope=all` fica disponivel
  explicitamente para diagnostico. Notas canceladas emitidas permanecem
  visiveis e nao entram nos totais financeiros ativos. `POST /exports`
  aceita `excel_nfse` alem de `zip_xml`, sempre filtrado por emitente e
  periodo inclusivo. O bootstrap local aceita `-AdnEnvironment` e
  `-TenantName`, preservando os valores existentes quando omitidos. O
  tenant mantem slug/login de desenvolvimento e pode ser exibido como
  "Vice Versa" sem cadastra-la como empresa coletada. Migration
  `0019_export_excel_nfse` adicionada.
  O helper mTLS tambem ganhou fallback seguro para Windows quando
  `os.fchmod` nao esta disponivel, mantendo `mkstemp` exclusivo e permissao
  restrita antes de gravar o PEM temporario.

- **PROD-READY** — Checklist de prontidao para producao criado em
  `docs/production-readiness-checklist.md`. Este passa a ser o backlog
  mestre de producao, enquanto este `STATE.md` segue como arquivo de
  atualizacao do andamento. A cada alteracao concluida rumo a producao,
  atualizar o item correspondente no checklist, registrar a evidencia
  neste arquivo e atualizar o `CHANGELOG.md` quando houver mudanca de
  comportamento, seguranca, deploy, API, worker ou UI.
  - **2026-08-07 - Stack Docker local completa (`nfse-local`):** ambiente
    isolado para Docker Desktop entregue com PostgreSQL, Redis, MinIO, API,
    worker, scheduler, web-app e Caddy, expondo somente
    `http://127.0.0.1:3000` (ou a primeira porta livre ate 3099). O bootstrap
    PowerShell gera segredos ignorados pelo Git, aplica migrations, cria o
    bucket, executa seed idempotente e abre o navegador com a conta local
    `admin@demo.local`. O login reservado e aceito somente com flag explicita
    em development. Durante o smoke foi corrigida a ativacao do RLS para usar
    `set_config(..., true)`, forma parametrizavel equivalente a `SET LOCAL` no
    PostgreSQL. Evidencias locais: build das tres imagens; todos os oito
    servicos long-running saudaveis e tres init jobs com exit 0; frontend com
    lint/typecheck/build verdes e 433 testes aprovados; Ruff verde e 11 testes
    Python direcionados aprovados (1 integracao ignorada sem banco de teste);
    login 200; listas de empresas, execucoes, agendamentos, ocorrencias e
    arquivos com 200; round-trip e URL pre-assinada do MinIO aprovados. Os
    containers antigos `nfse-postgres` e `nfse-redis` permaneceram intactos.
  - **2026-08-07 - Correcoes minimas de boot e login:** removido o `if`
    duplicado sem corpo em `apps/api/api/config.py`; a consulta de login passa
    a usar `CAST(:tenant_slug AS text)`, evitando `AmbiguousParameter` quando o
    slug nao e informado; e o teste de `dry_run` duplicado foi removido de
    `tests/test_jobs.py`. O deploy self-host da PR #168 ficou deliberadamente
    fora deste recorte. Evidencias locais: `ruff check .` verde; `py_compile`
    dos modulos alterados; 22 testes direcionados aprovados; smoke com
    PostgreSQL 16, migrations completas, signup 201 e login sem slug 200.
  - **2026-06-12 — PROD-READY 1.1 / refresh token chain revoke:**
    corrigida a CTE recursiva de `apps/api/api/security/tokens.py` para
    caminhar do token reutilizado para seus descendentes via `replaced_by`
    (`rt.id = c.replaced_by`). Evidencia local: `python -m pytest
    apps/api/tests/test_auth_tokens_unit.py -q` verde; a suite de
    integracao existente `test_refresh_reuse_detection_invalidates_chain`
    cobre o fluxo `/auth/refresh` com cadeia A -> B -> C quando
    `TEST_DATABASE_URL` estiver disponivel.
  - **2026-06-12 — PROD-READY 1.1 / auth hardening completo:**
    concluidos os demais itens de seguranca/autenticacao do bloco 1.1:
    login multi-tenant agora exige `tenant_slug` quando o usuario possui
    mais de uma membership ativa; `API_JWT_SECRET` passa a exigir pelo
    menos 32 bytes em staging/production; e o painel Next.js ganhou
    `middleware.ts` server-side para redirecionar rotas autenticadas sem
    cookie httpOnly de refresh para `/login?next=...`. Evidencias locais:
    `python -m pytest apps/api/tests/test_auth_jwt.py
    apps/api/tests/test_auth_tokens_unit.py -q`, `ruff check
    apps/api/api/auth apps/api/api/config.py apps/api/api/security/jwt.py
    apps/api/api/security/tokens.py apps/api/tests/test_auth_jwt.py
    apps/api/tests/test_auth_tokens_unit.py apps/api/tests/test_auth_routes_integration.py`,
    `pnpm --filter web-app typecheck`, e a suite de integracao de auth
    segue gated por `TEST_DATABASE_URL`.

  - **2026-06-12 — PROD-READY 1.2 e 1.3 / bloqueadores criticos do item 1 concluidos:**
    finalizados os itens restantes do bloco 1 do checklist de producao.
    Scheduler agora usa advisory lock transacional por tenant/company antes
    de verificar overlap e criar execution; `POST /executions` e
    `POST /reprocess` reaproveitam execution aberta equivalente para evitar
    duplicidade por retry; `worker_core.jobs.run_execution` respeita
    `dry_run` vindo do argumento/RQ meta sem upload XML, sem insert de
    `execution_items` e sem persistencia de NSU. O CI Python passa a rodar
    `pytest tests apps/api/tests apps/worker/tests -v`, o CI frontend passa
    a rodar `pnpm --filter web-app test`, e foram adicionados/corrigidos os
    testes de schema de reprocessamento, RQ/fakeredis, concorrencia do
    scheduler, smoke API->Redis/RQ->worker fake e idempotencia de execution.
    Evidencias locais: `python -m pytest apps/api/tests/test_reprocess_schemas.py -q`,
    `python -m pytest apps/api/tests/test_executions_idempotency_unit.py
    apps/api/tests/test_queue_unit.py -q`, `python -m pytest
    apps/worker/tests/test_main.py apps/worker/tests/test_scheduler.py -q`,
    `python -m pytest tests/test_jobs.py -q` e `ruff check` nos arquivos
    Python alterados.

  - **2026-06-12 — PROD-READY 2 / deploy e infraestrutura minima:**
    finalizados os itens versionaveis do bloco 2 do checklist de producao.
    Workflows de staging/prod agora publicam tres imagens (`nfse-api`,
    `nfse-worker`, `nfse-web-app`); o Compose de deploy ativa `migrate`,
    API, worker, scheduler e web-app com healthchecks; a API separa
    `/health` de `/ready`; `deploy.sh` valida `/ready` e documenta que o
    release executa `alembic upgrade head`; o rollback com migrations ficou
    formalizado em `infra/deploy/rollback.md`; Nginx de app/API agora aponta
    para `127.0.0.1:3000/8000`; o smoke S3 valida presigned URL; e Alembic
    prioriza `API_MIGRATION_DATABASE_URL` para separar conexao de migration.
    Permanecem bloqueios manuais inevitaveis no checklist (`[!]`): criar VPS,
    secrets GitHub, DNS/TLS e bucket/credenciais S3 reais. Evidencias locais:
    `ruff check apps/api/api/main.py apps/api/alembic/env.py
    apps/api/tests/test_observability_ready.py apps/worker/worker/scheduler.py
    apps/worker/tests/test_scheduler.py`, `python -m pytest
    apps/api/tests/test_observability_ready.py apps/worker/tests/test_scheduler.py -q`,
    `pnpm --filter web-app typecheck`, `python -m json.tool
    infra/s3-lifecycle.json` e `bash -n infra/deploy/deploy.sh
    infra/scripts/s3-smoke-test.sh`.

  - **2026-06-12 — PROD-READY 3 / robustez do fluxo de coleta:**
    finalizados os itens versionaveis do bloco 3. Chamadas HTTP ao ADN agora
    tem timeout explicito e retry/backoff parametrizados por `NFSE_ADN_*`;
    falhas do portal passam por `PortalRequestError` e sao mapeadas para
    codigos operacionais estaveis (`PORTAL_5XX`, `PORTAL_TIMEOUT`,
    `PORTAL_RATE_LIMIT`, `PORTAL_HTTP_ERROR`); `API_JOB_TIMEOUT_SECONDS`
    parametriza o timeout RQ para evitar jobs presos; o worker so avanca
    `last_nsu` quando a execution termina `succeeded`; falhas parciais de
    storage/DB ficam reconciliaveis por `packages/worker-core/scripts/reconcile_storage.py`;
    e o checklist registra as evidencias existentes de export ZIP, limite 2 GiB,
    presigned URL 1h e retencao de exports. Permanece bloqueada apenas a
    coleta real em staging com CNPJ/PFX autorizado, por depender de certificado
    e senha reais do owner. Evidencias locais: `python -m pytest
    tests/test_nfse_fetcher_config.py tests/test_jobs.py apps/api/tests/test_queue_unit.py -q`,
    `ruff check packages/worker-core/worker_core/fetcher.py
    packages/worker-core/worker_core/collector.py packages/worker-core/worker_core/jobs.py
    apps/api/api/queue.py apps/api/api/config.py tests/test_nfse_fetcher_config.py
    tests/test_jobs.py apps/api/tests/test_queue_unit.py`, e `python -m py_compile
    packages/worker-core/scripts/reconcile_storage.py`.

  - **2026-06-12 — PROD-READY 4 / observabilidade e operacao:**
    finalizados os itens versionaveis do bloco 4. API, worker e scheduler
    emitem JSON Lines com filtro de redacao para tokens, PFX, senhas,
    ciphertext e presigned URLs; o dashboard Grafana versionado agora cobre
    logs, fila RQ, scheduler, execucoes, codigos de ocorrencia e backup; o
    contrato de alertas (`infra/observability-alerts.md`) define sinais,
    janelas, severidades e runbooks; e foram adicionados runbooks/checklists
    para sessoes/refresh tokens, migrations com falha, restore completo,
    credencial invalida e simulacoes pre go-live. Permanece como etapa
    operacional a validacao real da stack Uptime Kuma/Grafana/Loki/Promtail
    na VPS por depender de DNS, acesso e segredos reais. Evidencias locais:
    `python -m pytest apps/api/tests/test_logging_redaction.py
    tests/test_worker_logging_redaction.py -q`, `python -m json.tool
    infra/compose/grafana/dashboards/api-worker-logs.json >/dev/null`, e
    `ruff check apps/api/api/logging.py apps/worker/worker/main.py
    apps/worker/worker/scheduler.py packages/worker-core/worker_core/logging.py
    apps/api/tests/test_logging_redaction.py tests/test_worker_logging_redaction.py`.

  - **2026-06-12 — PROD-READY 5 / produto, dados e LGPD:**
    item 5 organizado em artefatos versionados. `/legal` passa a publicar
    termos, privacidade, retencao e seguranca; signup aponta para as ancoras
    `/legal#terms` e `/legal#privacy`; `docs/legal/lgpd-ropa.md` documenta
    ROPA/base legal; `docs/legal/data-retention-policy.md` consolida retencao
    de XMLs, exports, logs, credenciais e backups; `docs/product/tenant-users-lifecycle.md`
    explicita lacunas de convites, owner protection, tenant switcher e
    suspensao/cancelamento; e `docs/product/billing-limits.md` organiza limites
    de plano, comportamento ao exceder quota e integracao futura de billing.
    Permanecem bloqueados os itens que exigem implementacao de endpoints
    `/tenant/*`, tenant switcher funcional, admin lifecycle de tenant e decisoes
    comerciais de nome/gateway/precos. Evidencias locais: `pnpm --filter
    web-app typecheck`, `pnpm --filter web-app lint` e `git diff --check`.

Trabalhos em aberto tambem seguem referenciados em
`docs/auditoria-tecnica-2026-04-22.md` (correcoes pendentes de
seguranca/CI/scheduler) e nas decisoes do final do arquivo (nome
comercial e gateway de pagamento).

## Concluidos (entregas recentes)

- **APP-11** — Wizard de onboarding (3 passos, modal persistente):
  novo pacote `apps/web-app/components/onboarding/` montado em
  `<RequireAuth>` (cobre todas as rotas autenticadas via
  `components/auth/require-auth.tsx`, sem tocar nos 6 layouts
  individuais). `<OnboardingWizard>` renderiza modal bloqueante
  enquanto o tenant nao concluiu os 3 passos. Deteccao do passo
  atual e 100% derivada do backend em `use-onboarding-state.ts`
  (nenhuma migration / flag nova):
  1. **Passo 1 (empresa)** ativo quando `listCompanies(pageSize=1)`
     devolve `total=0`. Form inline em `step-empresa.tsx` reusa
     `CNPJInput` (DS-07) + `isValidCnpj`/`normalizeCnpj` — schema Zod
     duplica deliberadamente ~20 linhas do `<NovaEmpresaDialog>` para
     nao refatorar a entrega APP-03. Chama `createCompany` direto.
  2. **Passo 2 (credencial)** ativo quando a 1a empresa existe mas
     `fetchCredential(companyId)` retorna `null` ou status !=
     `active` ou cert_not_after <= now. Form inline em
     `step-credencial.tsx` usa `FileDropzone` + `SecretField` (DS-07)
     e chama `uploadCredential` — reusa o mesmo mapa de `CredentialApiError`
     do dialog APP-04 (traducao humana: senha incorreta, PFX invalido,
     413 pfx_too_large, etc.).
  3. **Passo 3 (execucao)** ativo quando `listExecutions(status=
     "succeeded", page_size=1)` **e** `listExecutions(status=
     "partial", page_size=1)` ambos retornam `total=0`. Form em
     `step-execucao.tsx` enfileira uma coleta dos ultimos 30 dias
     da 1a empresa via `createExecutions` e polla `getExecution` a
     cada 2s (mesma cadencia de APP-05) ate estado terminal. Em
     `succeeded|partial`, dispara **uma vez** `postFirstCollectionDone`
     (novo cliente `lib/api/onboarding.ts`) que chama o endpoint
     `POST /onboarding/first-collection-done` — backend insere linha
     em `notifications` (`channel='email'`, `type='first_collection_done'`,
     `payload='{}'::jsonb`, `user_id=<sub>`, `tenant_id=GUC`) com
     idempotencia via lookup-antes-insert por (user_id, type, channel).
     Ate um consumer SMTP aparecer (ticket futuro), a linha permanece
     na outbox como `status='pending'`. Falha na notificacao nao
     bloqueia a UX — a tela de "parabens" abre mesmo assim.
  **Skip destacado (DoD)**: botao "Pular por enquanto" com texto muted
  e aviso "Nao recomendado: sem credencial a coleta nao pode iniciar"
  grava `Date.now()` em `localStorage` (`nfse:onboarding:dismissed:
  <tenantId>:<userId>`). `isDismissalActive` suprime o modal por 24h;
  apos expirar, wizard reaparece enquanto onboarding estiver
  incompleto. Quando completo (isComplete=true + user clicou "Finalizar
  1a coleta" que flipou o state via `refresh()`), mostra
  `<OnboardingCelebration>` uma unica vez — fechar limpa o dismiss
  (ja nao e preciso). Escolha de `<RequireAuth>` como host (nao de
  cada layout individual) garante que o wizard aparece em `/empresas`,
  `/execucoes`, `/ocorrencias` etc. sem duplicacao.
  Novo endpoint backend em `apps/api/api/onboarding/routes.py`
  (`POST /onboarding/first-collection-done`), registrado em
  `main.py`; schemas Pydantic em `apps/api/api/onboarding/schemas.py`
  (`FirstCollectionDoneOut` com `already_recorded` + `notification_id`).
  RBAC: `_AnyMember = require_role("owner","admin","operator","viewer")`
  — qualquer membro autenticado pode registrar, o wizard nao bloqueia
  viewer de concluir onboarding (o step 3 exibe aviso "sem permissao
  para disparar coleta" mas o banner persistente continua visivel).
  Testes: 5 de integracao em `apps/api/tests/test_onboarding_routes_integration.py`
  (feliz, idempotente, viewer pode registrar, sem token -> 401, RLS
  isola cross-tenant) gated por `TEST_DATABASE_URL`; 8 vitest em
  `apps/web-app/components/onboarding/onboarding-wizard.test.tsx`
  (sessao nao autenticada, 3 passos de fato renderizam, onboarding
  completo nao renderiza, skip grava localStorage e fecha, dismiss
  ativo suprime, dismiss expirado reabre). `pnpm typecheck` verde,
  `pnpm lint` zero warnings, `pnpm test` = 44 files / **398 passed**
  (8 novos vs 390 em main).
  **Drive-by fix (CHANGELOG `### Fixed`)**: trazidos pelo merge
  de `task/APP-05-execucoes` + `task/APP-02-dashboard`, os arquivos
  `apps/web-app/lib/api/{executions,occurrences}.ts` e
  `apps/web-app/components/app-shell/nav-items.ts` estavam em `main`
  com **artefatos de merge** (duplas declaracoes de interface,
  imports soltos, funcoes duplicadas com assinaturas conflitantes,
  array `NAV_ITEMS` nao fechado). TS declaration merging mascarou o
  erro em runtime mas `pnpm typecheck` explodia com ~50 erros de
  sintaxe. Reconstrucao minima: `executions.ts` e `occurrences.ts`
  aceitam agora inputs em camelCase (APP-05, APP-06) **ou**
  snake_case (APP-02 dashboard) — o serializador normaliza para
  snake_case no URL. `nav-items.ts` reunido em um unico array com
  todas as 11 rotas (Dashboard, Empresas, Execucoes, Agendamentos,
  Ocorrencias, Notas, Certificados, Tenants, Assinatura, Usuarios,
  Configuracoes). Nenhum consumidor precisou ser refatorado.
  Move APP-11 de "Bloqueadas" (deps APP-03 + APP-04 + APP-05 todas
  mergeadas em `main` via PRs #136/#133/#152) para "Em Andamento"
  (PR a abrir — Closes #59).
- **APP-07** — Pagina `/agendamentos` (UI de schedules cron):
  rota `apps/web-app/app/agendamentos/` (`layout.tsx` com
  `RequireAuth` + `AppShell`, `page.tsx` com header + view,
  `agendamentos-view.tsx` client com react-query consumindo
  `listSchedules`/`listSchedulePresets`/`listCompanies`).
  Lista renderiza tabela com colunas Empresa (resolve `company_id` ->
  `razao_social` via `GET /companies?page_size=100` client-side;
  `null` vira "Todas as empresas") | Quando (cron humanizado +
  `font-mono` com cron literal abaixo) | Timezone | Proximo run
  (formatado pt-BR) | Status (toggle `role=switch` `aria-checked` +
  `<StatusBadge>` Ativo/Pausado) | Acoes (editar/excluir). Toggle
  on/off faz `PATCH /schedules/{id} { enabled }` via mutation do
  react-query que invalida `[schedules:list]` em sucesso —
  **reflete em `next_run_at`** (DoD): backend recalcula quando
  `enabled` vira `true` e limpa quando vira `false`; em falha mostra
  mensagem inline no status. Excluir (owner|admin) usa `confirm()`
  nativo antes de `DELETE`. `<ScheduleFormDialog>` create/edit com
  `<Modal>` existente: builder amigavel com 4 modos
  (`daily|weekly|monthly|custom` via `role=radio`) + select de
  hora/minuto (+ dia da semana em weekly, dia do mes em monthly) +
  select de TZ (6 opcoes BR + UTC; preserva TZ existente fora da
  lista em edicao) + select de empresa (UUIDs) + checkbox ativar
  agora. Presets de `GET /schedules/presets` viram chips no topo
  (clique aplica via `cronToBuilder`). Painel "Expressao cron"
  mostra cron literal + preview "Proximos 5 runs ({TZ})" calculado
  client-side em `data-testid="next-runs"`; **cron invalida**
  (DoD) bloqueia submit e mostra `<p data-testid="cron-error">` com
  a mensagem do parser, tambem desabilitando o botao — com
  mensagens especificas para 400/403/404 vindos do backend.
  Novo modulo puro `apps/web-app/lib/schedules/cron.ts`:
  `parseField` (suporta `*`, `a-b`, `*\/N`, `a-b\/N`, `a,b,c` com
  validacao de range por campo), `parseCron`/`validateCron`
  (normaliza whitespace, exige 5 campos, mensagem curta em
  `CronParseError`), `humanizeCron` (casa presets e formas do
  builder — "Todo dia as HH:MM", "Toda segunda-feira as HH:MM",
  "Todo mes no dia D as HH:MM", "A cada minuto"; fallback
  "Cron customizado: <expr>"), `computeNextRuns` (minuto a minuto,
  matches via `Intl.DateTimeFormat` com `timeZone` para honrar DST
  + lookahead 2 anos p/ evitar loop em `0 0 31 2 *`; convencao
  Unix para dia+dow: OR quando ambos restritos, AND quando um e
  wildcard), `builderToCron`/`cronToBuilder` (round-trip entre os
  4 modos do builder). Novo cliente HTTP
  `apps/web-app/lib/api/schedules.ts` (`listSchedules` com filtros
  `enabled|company_id`, `getSchedule`, `listSchedulePresets`,
  `createSchedule`, `updateSchedule`, `toggleSchedule` — atalho que
  delega em `updateSchedule({ enabled })`, `deleteSchedule`,
  `extractErrorDetail` para FastAPI-style `{ detail }`).
  `nav-items.ts` ganha item "Agendamentos" (icone `CalendarClock`)
  entre "Empresas" e "Notas". RBAC alinhado a matriz: leitura e
  toggle bloqueado para viewer (UI desabilita toggle + oculta
  Novo/Editar/Excluir quando papel insuficiente; backend ja devolve
  403 com mensagem clara repassada na UI). 35 testes vitest de
  cron (`parseField` 6, `parseCron` 4, `validateCron` 2,
  `normalizeCronExpr` 1, `humanizeCron` 7, `computeNextRuns` 6 —
  com caso cross-TZ `0 3 * * *` em `America/Sao_Paulo` -> 06:00Z
  e weekly picking segunda-feira, `builderToCron` 5,
  `cronToBuilder` 4) + 12 do cliente HTTP (`listSchedules` query
  building, header Authorization, presets unwrap, create/patch/
  toggle/delete, ApiError em 400/403, `extractErrorDetail`) + 7
  testes de view (RBAC viewer/owner/admin/operator, linha com cron
  humanizado, toggle desabilitado em viewer, toggle chama
  `toggleSchedule(false)` em agenda ativa, excluir sim/nao por
  papel, empty state) + 7 de dialog (render default + 5 runs,
  aplicar preset, cron customizada invalida mostra erro e
  desabilita submit, submit feliz chama `createSchedule` com
  payload correto, ApiError 400 vira alert, 403 mostra mensagem
  clara, edicao pre-preenche e chama `updateSchedule`). Suite
  completa: `pnpm test` = 300 passed em 30 files (253 -> 300;
  +47 novos); `tsc --noEmit` verde; `next lint` sem warnings. Sem
  E2E Playwright novo — escolha deliberada: o dialog + toggle
  tem cobertura rasa de jsdom suficiente e nao ha fluxo multi-
  pagina no ticket. API-12 (CRUD `/schedules`) ja estava em
  `main` via PR #130 — nova nota em
  `docs/architecture/rbac-matrix.md` nao foi necessaria
  (API-12 ja incluiu a secao Schedules). Move APP-07 de
  "Bloqueadas" (dependencia API-12 ja mergeada) para
  "Em Andamento" (PR a abrir — Closes #55).

- **APP-06** — Inbox `/ocorrencias` consumindo API-09. Nova rota
  `apps/web-app/app/ocorrencias/` com `layout.tsx` (RequireAuth +
  AppShell, igual `/empresas`), `page.tsx` + `OcorrenciasView` +
  `OcorrenciasTable` usando `<DataTable>` (DS-06) com filtros
  server-side: `status` (select 5-valores: open/ack/snoozed/resolved/
  ignored), `severity` (select 4-valores: info/warning/error/critical) e
  `company_id` (text UUID — seletor rico fica para ticket futuro quando
  houver `GET /companies` global + `GET /users`). Colunas: `code`+label
  (link para `/ocorrencias/[id]`), severity/status via `StatusBadge`
  (DS-04) mapeados em `severityVariant`/`statusVariant`, `title` (tooltip
  com `detail`), `last_seen_at`, `first_seen_at`. Cliente HTTP novo
  `apps/web-app/lib/api/occurrences.ts` (tipos `Occurrence`/
  `OccurrenceListResponse`/`OccurrenceSeverity`/`OccurrenceStatus`,
  funcoes `listOccurrences`/`getOccurrence`/`acknowledgeOccurrence`/
  `resolveOccurrence`/`assignOccurrence`, helper `isTerminal`, labels
  pt-BR). Detalhe em `apps/web-app/app/ocorrencias/[id]/` —
  `OccurrenceDetailView` client component com `useQuery`
  (`["ocorrencias:detail", id]`) + 3 `useMutation` que chamam
  `queryClient.setQueryData` no retorno (**DoD "acoes atualizam estado
  sem reload"**) e invalidam `[OCORRENCIAS_QUERY_KEY]`. Acoes gated por
  RBAC (owner/admin/operator): **Reconhecer** so em `open`; **Resolver**
  so em nao-terminais, abre `ResolveDialog` (react-hook-form + zod,
  note 1..2000 chars obrigatoria, erro explicito em 409/422/403);
  **Atribuir** sempre (`AssignDialog` com validacao UUID regex, erro
  404 "usuario nao e membro do tenant"); **Reprocessar** = `<Link>` para
  `/execucoes/nova?reprocessar_de=<id>&company_id=<cid>` (APP-05 consome
  quando chegar — nota no tooltip). Runbook inline em `RunbookPanel`:
  faz GET `/api/runbooks/<slug>`, renderiza com `react-markdown` +
  `remark-gfm` e componentes customizados (heading/p/ul/ol/code/pre/a/
  blockquote estilizados via Tailwind — sem `@tailwindcss/typography`).
  Route handler `apps/web-app/app/api/runbooks/[slug]/route.ts` (runtime
  Node) le `docs/runbooks/<slug>.md` com `readFile` a partir de
  `process.cwd()/../..`, allowlist por `isRunbookSlug` (evita path
  traversal), `Content-Type: text/markdown; charset=utf-8`. Catalogo em
  `apps/web-app/lib/occurrences/codes.ts` mapeia os 11 codigos
  documentados em `docs/architecture/occurrence-codes.md` para
  `{label, severity_default, runbookSlug}` — codigos nao catalogados
  caem em "Outro" sem quebrar a listagem. 4 runbooks novos criados em
  `docs/runbooks/` (**reprocessamento.md**, **parse-error.md**,
  **storage-error.md**, **erro-desconhecido.md**) cobrindo os codigos
  `REPROCESS_NEEDED`, `PARSE_ERROR`, `STORAGE_ERROR` e `UNKNOWN`
  (sintomas, diagnostico, mitigacao, escalacao, prevencao). Tabela de
  codigos em `docs/architecture/occurrence-codes.md` atualizada: zero
  "(em redacao)", todos os 11 codigos linkam para runbook — **DoD "10
  codigos com runbook"** cumprido com folga. Aba `occurrences-tab.tsx`
  do detalhe de empresa (APP-03) substituida: stub vira call-to-action
  com `<Link>` para `/ocorrencias?company_id=<id>` (filtro persistido
  pelo DataTable via URL state). Item "Ocorrencias" (icon `AlertCircle`)
  adicionado em `components/app-shell/nav-items.ts` entre "Empresas" e
  "Notas". Novas deps em `apps/web-app/package.json`:
  `react-markdown ^9.0.1` + `remark-gfm ^4.0.0` (~30kB gzip). 22 testes
  vitest novos: `lib/api/occurrences.test.ts` (17 — buildListQuery,
  list/get/ack/resolve/assign com Authorization, propagacao de ApiError
  403/404/422, helper `isTerminal`) + `app/ocorrencias/[id]/
  occurrence-detail-view.test.tsx` (5 — render de header, RBAC gating
  viewer sem botoes, acknowledge invalida cache, reprocessar tem query
  string correta, estado terminal oculta ack/resolve mas mantem
  atribuir). `pnpm typecheck` verde, `next lint` zero warnings,
  `vitest run` 261 passed (239 existentes + 22 novos). Dependencia
  API-09 ja satisfeita (PR #127 merged)
  (PR a abrir — Closes #54).
- **APP-05** — `/execucoes/nova` + acompanhamento real-time.
  Novo cliente `apps/web-app/lib/api/executions.ts` com tipos
  alinhados a API-07/API-08 (`Execution`, `ExecutionItem`, envelopes
  paginados, `CreateExecutionsPayload`, `CreatedExecution`), funcoes
  `listExecutions`/`getExecution`/`listExecutionItems`/
  `createExecutions` via `apiFetch` (APP-01) e `ExecutionsApiError`
  mapeando 401/403/404/422/502 em codigos canonicos
  (`companies_not_found`, `credential_missing_or_expired`,
  `queue_unavailable`, `validation_error`, `forbidden`, `not_found`,
  `network`, `unknown`) — o 422 estruturado do backend preserva
  `company_ids`/`missing` pra UI citar quais CNPJs travaram a
  submissao. Helpers `decideExecutionBadge` (mapeia os 6 status pra
  variantes `<StatusBadge>`: queued->pending, running->processing,
  succeeded->success, failed->failed, cancelled->blocked,
  partial->warning), `computeProgress` (clampa em 100%, lida com
  `total=0` em queued sem div/0) e `isTerminalStatus`. Nova rota
  protegida `apps/web-app/app/execucoes/` com 3 paginas: (a)
  `/execucoes` — lista paginada server-side filtrando por `status`,
  CTA "Nova execucao" apontando pra `/execucoes/nova`, paginacao
  Anterior/Proxima e empty-state com link pra criar; (b)
  `/execucoes/nova` — formulario client (`NovaExecucaoForm`) com
  multi-select de companies ativas (usa `listCompanies` com
  `filters: {status: 'active'}` e page_size 100, exibe CNPJ formatado
  + razao + UF), `<PeriodPicker>` (DS-07, default `last_30d`),
  toggle dry-run, toggle "Incremental desde ultimo NSU" (UX
  informativa apontando que o worker ja respeita `last_nsu`
  internamente — periodo define a janela, nao o piso de NSU), CTA
  "Iniciar" chamando `createExecutions` e redirecionando pra
  `/execucoes/{id}` em N=1 ou `/execucoes` em N>1. Viewer ve alerta
  "sem permissao" (DoD RBAC), operator/admin/owner veem o form. Em
  422 `credential_missing_or_expired` traduz a mensagem listando os
  CNPJs afetados com orientacao pra regularizar na aba Credencial
  (APP-04) — evita N+1 no front pre-filtrando e alinha com a linha
  "nao validar o que o backend ja valida"; (c) `/execucoes/[id]` —
  `ExecucaoDetailView` com header (StatusBadge, CNPJ curto, periodo,
  indicador "Atualizando a cada 2s" quando nao terminal), barra
  `role="progressbar"` com `aria-valuenow={ok+fail}` e
  `aria-valuemax={total}`, KPIs (total/ok/fail/iniciada), tabela de
  items com filtro por status (tabs Todos/OK/Falhou/Ignorados/
  Pendentes), paginacao, checkbox por linha + "Selecionar todos
  visiveis", botao "Reprocessar selecionados (N)" com
  `aria-disabled=true` + `title` explicando "liberado com APP-06 /
  API-10" (stub consciente sem bloquear o DoD quando o endpoint
  chegar). **Polling 2s** via `refetchInterval` do react-query
  (`query.state.data` em `isTerminalStatus` -> desliga o polling;
  ainda em andamento -> 2000ms), aplicado tanto ao detail quanto aos
  items — quando `status` vira `succeeded`/`failed`/`cancelled`/
  `partial` o polling cessa automaticamente. Sidebar
  `components/app-shell/nav-items.ts` ganha item "Execucoes" (icone
  `PlayCircle`) entre "Empresas" e "Notas". Stub `executions-tab.tsx`
  da aba de empresa (APP-03) deixa de ser informativo e mostra as 5
  execucoes mais recentes daquela company com atalho "Nova execucao"
  pra `/execucoes/nova?company_id={id}` (pre-selecao para fluxo
  futuro). Testes vitest: (a) `lib/api/executions.test.ts` com 16
  casos (buildListQuery/buildItemsQuery com defaults e filtros,
  listExecutions Authorization, getExecution 404, listExecutionItems
  endpoint correto, createExecutions POST JSON feliz + traducao de
  422 `credential_missing_or_expired` preservando `companyIds`, 422
  `companies_not_found`, 502 `queue_unavailable`, `decideExecutionBadge`
  pros 6 status, `isTerminalStatus` e `computeProgress` incluindo
  clamp 100% e divisao por zero); (b)
  `app/execucoes/nova/nova-execucao-form.test.tsx` com 7 casos
  (viewer ve alerta sem permissao, operator ve form, submissao de 1
  empresa redireciona pra `/execucoes/{id}`, submissao de N empresas
  redireciona pra `/execucoes`, dry_run propaga no payload, 422
  credential traduz com CNPJs formatados no alert, 502 queue mostra
  mensagem de fila indisponivel); (c)
  `app/execucoes/[id]/execucao-detail-view.test.tsx` com 7 casos
  (progressbar com `aria-valuenow/max` corretos, indicador polling
  visivel em running, ausente em succeeded, refaz query detail apos
  2s enquanto nao-terminal (real timers, timeout 10s), 404 exibe
  mensagem clara, filtro por status refaz query com `status=failed`,
  botao Reprocessar `aria-disabled=true` + title citando
  APP-06/API-10). E2E Playwright `e2e/execucoes.spec.ts` intercepta
  `/companies`/`/executions`/`/executions/{id}`/`/executions/{id}/items`
  via `page.route` cobrindo DoD literal: cria (selecionar empresa +
  Iniciar), acompanha (progressbar visivel), ve itens aparecendo
  (data-item-id=i1 e i2 apos 2a chamada do polling). `pnpm
  typecheck`, `pnpm lint` (`next lint`) e `pnpm test` (`vitest run`)
  verdes — 29 arquivos / 269 specs (135 anteriores + 30 novos de
  APP-05 + diff dos outros tickets mergeados). Backend intocado
  (API-07/API-08 ja em main). `POST /executions` precisa de Redis
  pra pre-ping (502 sem tocar DB se fila offline) — o caminho feliz
  local e coberto estruturalmente pelos mocks do vitest + page.route
  do Playwright. Move APP-05 de "Bloqueadas" (deps API-07/API-08 ja
  mergeadas em main) para "Em Andamento"
  (PR a abrir — Closes #53).

- **APP-02** — Dashboard com KPIs em `/dashboard`
  (`apps/web-app/app/dashboard/page.tsx` passa a renderizar
  `<DashboardView/>` — substitui o stub de KPIStatCards em `empty`).
  Novo diretorio `apps/web-app/components/dashboard/` com 3
  componentes client: `dashboard-view.tsx` orquestra header + atalhos
  "Nova execucao" (`/execucoes/nova`, destino de APP-05) e "Ver
  ocorrencias" (`/ocorrencias`, destino de APP-06, mesmo padrao
  placeholder usado por `nav-items.ts`); `PeriodPicker` (DS-07)
  controlado localmente em `useState` inicializado via
  `computePresetRange("current_month")` (persistencia em URL fica como
  follow-up — escopo enxuto deste PR); `kpi-cards.tsx` renderiza os
  4 `<KPIStatCard>` (DS-05) consumindo react-query em paralelo
  (existente `AppQueryClientProvider` no RootLayout, `staleTime=30s`);
  `recent-timeline.tsx` lista as 10 execucoes mais recentes do
  periodo com dot por status (`CheckCircle2`/`AlertTriangle`/`XCircle`
  /`Loader2 animate-spin`/`Clock`/`MinusCircle`), linkando cada item
  para `/execucoes/{id}` (destino APP-05). Componente `<Timeline>`
  canonico do DS-08 ainda bloqueado — a lista provisoria fica isolada
  nesta pagina com comentario `@deprecated ao entregar DS-08` e
  sera substituida sem mudar a API publica quando DS-08 pousar.
  KPIs implementados:
  1. **"Notas coletadas no periodo"** — consome `GET /executions` com
     `page_size=100` + `from`/`to` do `PeriodRange`, soma `items_ok`
     client-side. Se `total > 100`, marca valor como aproximado
     formatando `1.234+` e troca o hint para "Soma aproximada
     (agregacao server-side em follow-up)." — follow-up `?aggregate=1`
     em API-08 ou novo endpoint registrado como debito tecnico.
  2. **"Execucoes OK / total"** — 2 chamadas paralelas com
     `page_size=1` a `GET /executions` (uma sem filtro, outra com
     `status=succeeded`) usando apenas o `total` do envelope. Exibe
     `<ok> / <total>` formatado em pt-BR; estado `empty` quando
     `total=0` no periodo.
  3. **"Ocorrencias abertas"** — `GET /occurrences?status=open&page_size=1`
     usando o `total` do envelope. **Nao** filtra por periodo
     (inbox reflete estado atual, nao a janela do dashboard — decisao
     explicita anotada no codigo).
  4. **"Certificados a vencer em 30d"** — permanece em
     `state="empty"` com hint "Disponivel apos endpoint REST de
     credenciais (follow-up)." porque API-06 popula
     `company_credentials.cert_not_after` mas ainda NAO expoe listagem
     REST agregada — `GET /companies/{id}/credential` (unitario) nao
     serve para contar vencimentos do tenant. Follow-up: expor
     `GET /credentials?expiring_in_days=30` antes de APP-05 (fora da
     trilha APP, fica como debito tecnico rastreavel).
  Clientes API novos: `apps/web-app/lib/api/executions.ts`
  (`listExecutions(params, ctx)` + `periodDateToUtcIso(day, boundary)`
  que mapeia `YYYY-MM-DD` do `PeriodRange` para ISO 8601 UTC com `to`
  exclusivo — a API filtra `started_at < to`, entao `endExclusive`
  avanca 1 dia; `EXECUTION_STATUS_LABEL` em pt-BR) e
  `apps/web-app/lib/api/occurrences.ts` (`listOccurrences`). Ambos
  reusam `apiFetch` de `lib/auth/api-client.ts` (injeta access token
  em memoria + refresh automatico em 401) e a interface
  `ApiCallContext` exportada de `lib/api/companies.ts`. Erros HTTP
  propagam como `ApiError(status, detail)` — react-query trata via
  `isError` e os componentes renderizam `state="error"`/mensagem
  dedicada no KPIStatCard ou no timeline. Filtro de periodo vai
  para ambos via `periodToApiWindow()` em `kpi-cards.tsx`;
  query keys incluem `[period.from, period.to]` para cache
  correto por janela. Layout grid: 4 cards responsivos
  (`grid-cols-1 sm:grid-cols-2 xl:grid-cols-4`), PeriodPicker em
  card com border/shadow alinhado ao DS-03, timeline em card
  com header descritivo ("Ultimas execucoes — As 10 execucoes mais
  recentes no periodo selecionado"). Specs vitest em
  `apps/web-app/components/dashboard/dashboard-view.test.tsx`
  (5 casos): (1) renderiza os 4 KPIStatCards, `role="group"` do
  PeriodPicker, links dos atalhos com `href` correto; (2) 10 items
  na timeline com link `/execucoes/exec-1`; (3) mensagem "Nenhuma
  execucao registrada no periodo" quando lista vazia; (4) KPI
  "Ocorrencias abertas" exibe `total` do envelope (7); (5) KPI
  "Certificados a vencer" permanece `data-state="empty"` (prova
  defensiva do follow-up). Mocks de `useAuth`, `listExecutions`,
  `listOccurrences` e `next/navigation`, seguindo mesmo padrao de
  `empresas-view.test.tsx`. `pnpm typecheck` e `pnpm lint` verdes;
  `pnpm test` = 27 arquivos / 244 testes (5 novos). DoD "< 1s com
  dados de teste" cumprido estruturalmente — as 4 chamadas rodam em
  paralelo (react-query default), com cache de 30s do
  `AppQueryClientProvider`; validacao manual de performance fica a
  cargo do owner apos deploy. "Links levam as telas corretas":
  timeline -> `/execucoes/{id}` (APP-05), atalhos ->
  `/execucoes/nova` (APP-05) e `/ocorrencias` (APP-06), KPIs sem
  navegacao. Move APP-02 para "Em Andamento" (deps DS-05 e API-08
  ambas mergeadas em `main`) (PR a abrir — Closes #50).
- **DS-09** — Cliente API tipado gerado do OpenAPI: nova camada em
  `apps/web-app/lib/api/` com `generated/schema.d.ts` (tipos emitidos
  por `openapi-typescript` v7 a partir do OpenAPI da `apps/api`),
  `client.ts` (factory `createApiClient` + singleton
  `getApiClient`/`configureApiClient`/`__resetApiClientForTests`
  baseados em `openapi-fetch` v0.13), `types.ts` (re-exports de
  `paths`/`components`/`operations`/`Schemas`), `hooks.ts` (hooks
  react-query base `useHealth`/`useVersion`/`useMe`/`useCompanies`/
  `useExecutions`, cada um aceitando `client` opcional para testes) e
  `README.md`. Middleware de auth em duas pontas: (1) `onRequest`
  injeta `Authorization: Bearer <token>` quando `getAccessToken`
  devolve token nao-nulo e o header ainda nao esta setado; (2)
  `onResponse` trata 401 chamando `tryRefresh()` da APP-01, retenta a
  request **uma unica vez** marcando header sentinela `x-ds09-retry:
  1` (evita loop), propaga o novo token via `onTokenRefreshed` e, em
  falha do refresh, chama `onAuthFailure` (default:
  `window.location.href = "/login"`). Script
  `apps/web-app/scripts/generate-api.mjs` (expoe
  `pnpm --filter web-app generate-api`) aceita `--url`/`--file` ou
  env `API_OPENAPI_URL` (default `http://localhost:8000/openapi.json`),
  chama `openapiTS` + `astToString` programaticamente e so reescreve
  `generated/schema.d.ts` quando o conteudo muda (idempotencia do DoD
  "re-run e idempotente" validada manualmente rodando o script duas
  vezes — segunda execucao imprime `sem mudancas`). Novas deps em
  `apps/web-app/package.json`: `openapi-fetch@^0.13` (run) e
  `openapi-typescript@^7` (dev). 8 testes vitest novos
  (`lib/api/client.test.ts` com 5 casos — injecao de Authorization,
  ausencia de token, retry em 401 com refresh bem-sucedido,
  `onAuthFailure` quando refresh falha e prova de nao-loop com
  header sentinela — e `lib/api/hooks.test.tsx` com 3 — `useHealth`
  feliz, `useCompanies` com querystring, propagacao de erro 500).
  Clientes legados (`lib/api/companies.ts`, `lib/auth/api-client.ts`,
  `lib/users/api-client.ts`, `lib/companies/credentials.ts`)
  **preservados sem alteracao** — migracao para o novo cliente fica
  para tickets especificos de cada trilha APP. `pnpm --filter web-app
  typecheck` verde, `next lint` zero warnings, `vitest run` =
  247 passed (228 anteriores + 8 novos DS-09 + rebalanceamento da
  suite). Move DS-09 de "Bloqueadas" (dependencias DS-01 e API-01 ja
  concluidas) para "Em Andamento"
  (PR a abrir — Closes #48).

- **API-14** — Scheduler de execucoes agendadas em
  `apps/worker/worker/scheduler.py`. Processo separado (entry point
  `python -m worker.scheduler` ou script `nfse-scheduler`) com
  `apscheduler.BlockingScheduler` rodando `CronTrigger(minute="*",
  timezone="UTC")` com `coalesce=True`/`max_instances=1`/
  `misfire_grace_time=30` — dispara `run_tick()` a cada minuto. Tick:
  (1) `SELECT id, tenant_id, company_id, cron_expr, timezone FROM
  schedules WHERE enabled=true AND next_run_at IS NOT NULL AND
  next_run_at <= :now` via `worker_core.db.get_admin_session`
  (BYPASSRLS — schedules vivem em varios tenants); (2) para cada
  schedule devido abre `get_tenant_session(tid)` (RLS via `SET LOCAL
  app.current_tenant`) e resolve companies alvo — `company_id`
  preenchido -> 1 row em `companies WHERE id = :cid AND deleted_at IS
  NULL`; NULL -> todas as companies ativas do tenant (`WHERE
  deleted_at IS NULL ORDER BY created_at ASC, id` — schedule
  "tenant-wide"); (3) para cada company faz check de overlap `SELECT
  1 FROM executions WHERE company_id = :cid AND status IN
  ('queued','running') LIMIT 1` — se existir, insere occurrence
  `SCHEDULE_OVERLAP` (severity `warning`, title "Disparo agendado
  pulado por sobreposicao", detail `schedule_id=<uuid>
  cron=<expr>`) e pula sem criar execution; caso contrario, INSERT
  em `executions` (trigger=`schedule`, status=`queued`,
  `period_start`/`period_end = CURRENT_DATE`) e enfileira
  `worker_core.jobs.run_execution` via RQ na mesma fila usada por
  API-07 (`API_REDIS_URL` + `API_QUEUE_NAME`, `job_timeout=3600`,
  `result_ttl=86400`, `failure_ttl=604800`, `meta={"tenant_id":
  str(tid), "trigger": "schedule"}`); (4) enqueue falha pos-INSERT
  marca a execution como `failed` com `error_summary=
  'enqueue_failed' + finished_at=now()`; (5) recalcula `next_run_at`
  via novo `apps/worker/worker/cron_utils.py` (duplica
  `apps/api/api/schedules/cron.py` com nota de fonte canonica —
  mesmo padrao de `worker_core/crypto.py` do API-13) passando
  `base=tick_now` para determinismo; `last_run_at = now()` so e
  marcado quando ao menos 1 execucao foi criada (tick so de overlap
  nao "relogia" o schedule mas ainda avanca `next_run_at` para
  evitar loop). Cron invalido -> log `scheduler.tick.cron_invalid`
  e pula a linha sem atualizar campos (preserva `next_run_at` para
  o owner investigar). Graceful shutdown: SIGTERM/SIGINT chamam
  `scheduler.shutdown(wait=True)` — combine com `stop_grace_period:
  30s` no compose. Log estruturado em cada etapa: `scheduler.boot`,
  `scheduler.tick.start/empty/fired/overlap/done`,
  `scheduler.tick.cron_invalid`,
  `scheduler.tick.enqueue_failed`,
  `scheduler.tick.companies_lookup_failed`,
  `scheduler.signal.received`, `scheduler.shutdown_failed`,
  `scheduler.exit`. Novas deps run em `apps/worker/pyproject.toml`:
  `apscheduler>=3.10`, `croniter>=2.0`; novo script entry-point
  `nfse-scheduler = "worker.scheduler:main"`. `docs/architecture/
  occurrence-codes.md` ganha linha `SCHEDULE_OVERLAP` (severity
  `warning`). README do worker ganha secao "Scheduler (API-14)"
  com instrucoes de rodar local + override de `CMD` no compose
  reusando a mesma imagem `nfse-worker`. Sem mudanca em
  `infra/compose/docker-compose.deploy.yml` (o servico `worker`
  ainda esta comentado la — o scheduler entra junto quando o owner
  habilitar deploy, reusando a mesma imagem). Testes: 11 em
  `apps/worker/tests/test_cron_utils.py` + 11 em
  `apps/worker/tests/test_scheduler.py` cobrindo a DoD (cron `* * * * *`
  dispara e loga; overlap cria occurrence sem duplicar execucao).
  `pytest apps/worker/tests/` = 34 passed; `pytest tests/test_jobs.py
  tests/test_db_nsu.py tests/test_crypto_worker.py` = 32 passed
  (suite existente do worker-core segue verde apos o drive-by fix em
  `jobs.py`). Inclui drive-by fix em `packages/worker-core/worker_core/
  jobs.py`: remove 34 linhas de docstring orfa do API-13 que
  sobreviveu a um merge conflict resolvido incorretamente no PR
  #140 (API-15) causando `SyntaxError: invalid character '—'
  (U+2014)` em qualquer import de `worker_core` — bloqueio real
  descoberto ao instalar o scheduler em editable mode e confirmado
  por `python -c "import worker_core"` apos o fix. Move API-14 de
  "Bloqueadas" (deps API-12 + API-13 mergeadas em main) para "Em
  Andamento" (PR a abrir — Closes #38).
- **API-10** — Reprocess jobs: novo pacote
  `apps/api/api/reprocess/` (`routes.py` + `schemas.py` +
  `__init__.py`) expondo `POST /reprocess` (RBAC
  `owner|admin|operator`) e `GET /reprocess/{id}` (todos os papeis)
  sobre a tabela `reprocess_jobs` (DATA-04 / migration 0007). O POST
  aceita **exatamente 1** de 3 escopos (`ReprocessIn` com
  `extra='forbid'` + `model_validator`): (1) `execution_item_ids[]` —
  agrupa items pela execution-pai via JOIN e cria 1 execution filha
  por tupla `(company_id, period_start, period_end)` distinta
  (items nao encontrados -> 422 `execution_items_not_found`); (2)
  `company_id + nsus[]` — infere periodo via
  `MIN/MAX(data_emissao)` dos items com NSU ∈ lista (fallback
  defensivo `[today, today]` quando nenhum item bate — o worker
  refara a coleta no dia); (3) `company_id + period{start,end}` com
  `statuses[]` opcional (auditado em `reprocess_jobs.scope` para
  rastreio, mas o worker atual refaz a janela inteira). Reusa
  `_validate_companies`/`_validate_credentials` de
  `executions/routes` (422 em company alheia ou sem credencial
  ativa). Pre-pinga Redis (502 sem tocar DB). Persiste linha em
  `reprocess_jobs` (status `queued`, `scope` jsonb canonizado com
  `kind`+payload, `created_by_user_id`) + N `executions` com
  `trigger='reprocess'` e enfileira `worker_core.jobs.run_execution`
  via `enqueue_run_execution` — mesmo pipeline de API-07. Falha de
  enqueue por execution marca a linha `failed` +
  `error_summary='enqueue_failed'`; se **todas** falharem, o
  `reprocess_job` vira `failed` com `error_summary='enqueue_failed_all'`
  e `finished_at=now()`. `result_execution_ids` atualizado apos os
  INSERTs. Audit log `reprocess.create` grava `scope_kind` +
  `executions_count` + `dry_run` (sem vazar company/period). GET
  deriva `progress` via JOIN com `executions.id = ANY(result_execution_ids)`
  — contadores por status + `effective_status` agregado (`running`
  se alguma in-flight, `succeeded`/`partial`/`failed`/`cancelled` apos
  todas terminarem; `partial` em mistura ok+failed). Coluna `status`
  do job-pai permanece `queued` porque o worker atual nao reconcilia
  — ticket futuro pode estender `run_execution` para atualizar.
  **Granularidade**: o worker sempre refaz a janela
  `(company, period_start, period_end)` da execution filha (portal
  Nacional pagina por NSU global e nao aceita lista de NSUs); a
  idempotencia do unique parcial `uq_execution_items_tenant_chave`
  (0005) garante que items ja `ok` nao duplicam, e items `failed`
  voltam a ser tentados — cobrindo a DoD "forca falha em 3 items,
  reprocessa 1, v2 atualiza status". Router registrado em
  `apps/api/api/main.py`. Matriz `docs/architecture/rbac-matrix.md`
  ganha secao "Reprocess (API-10)" e o placeholder invalido
  `POST /executions/{id}/reprocess` da secao Executions e substituido
  por nota apontando para `/reprocess`. 20 unit tests em
  `apps/api/tests/test_reprocess_schemas.py` (dedup de items/nsus/
  statuses, 3 combinacoes escopo-unico proibidas, `extra='forbid'`,
  period invalido, status nao-canonico) + 19 integration tests em
  `test_reprocess_routes_integration.py` gated por
  `TEST_DATABASE_URL` + fakeredis (3 escopos felizes, cross-tenant
  422 nos items, id inexistente, fallback de today, company
  inexistente/sem credencial 422, viewer 403/200, operator autorizado,
  Redis offline 502 + DB intocado, enqueue falha em todas -> job-pai
  failed, GET cross-tenant 404, effective_status running/succeeded/
  partial, GET 404 inexistente, audit log sem vazar scope, DoD E2E
  simbolico reprocessando 1 de 3 items). Sem migration nova —
  `reprocess_jobs` ja existia desde DATA-04. Move API-10 de
  "Bloqueadas" (API-08 mergeada) para "Em Andamento" (PR a abrir —
  Closes #34).
- **API-13** — Worker consumer (Redis -> worker-core E2E):
  `apps/worker/` RQ consumer orquestrando execucao ponta-a-ponta +
  novos adapters em `packages/worker-core/worker_core/`. Handler
  picado pelo RQ em `worker_core.jobs.run_execution(execution_id)`
  (a **mesma string** enfileirada por API-07 em
  `apps/api/api/queue.py` — por isso o handler vive em
  `worker_core.jobs`, nao em `apps/worker/`). Fluxo: (1) le
  `executions`+`companies`+`company_credentials` (admin + tenant
  sessions com `SET LOCAL app.current_tenant`), (2) decifra PFX +
  senha via `worker_core.crypto.decrypt` (envelope AES-256-GCM
  compativel com API-06 — mesmo `_VERSION_TAG`/HKDF salt/KEK env
  `API_CREDENTIAL_KEK_B64`, duplicacao intencional com comentario
  apontando pra fonte canonica em `apps/api/api/crypto.py`), (3)
  chama `fetch_nfse` (CORE-04) com `DbNsuSource` (persiste
  `companies.last_nsu` via UPDATE only-if-greater, invariante "NSU
  nunca regride") + callback que INSERT-a `execution_items` com
  `ON CONFLICT (tenant_id, chave_nfse) DO NOTHING` (**idempotencia**
  — retry do job nao duplica itens, satisfazendo DoD "crash no meio
  do job + retry") e sobe o XML pro S3 via `S3StorageClient` (CORE-05),
  (4) marca `executions.status` como `succeeded`/`partial`/`failed`
  via `_decide_final_status` (`fatal_rejected` -> failed; nenhum
  item + sem falha -> succeeded; fails > 0 com 0 ok -> failed; fails
  ou storage_errors > 0 com ok > 0 -> partial; tudo ok -> succeeded),
  (5) cria `occurrences` categorizadas (`CRED_INVALID`,
  `CERT_EXPIRED`, `PORTAL_5XX`, `PARSE_ERROR`, `STORAGE_ERROR`,
  `UNKNOWN`) alinhadas com `docs/architecture/occurrence-codes.md`.
  `apps/worker/` expoe entry point `python -m worker.main` lendo
  `API_REDIS_URL`+`API_QUEUE_NAME`+`WORKER_HEALTHZ_PORT` com
  handlers SIGTERM/SIGINT para graceful shutdown (RQ drena o job
  atual — compose deve setar `stop_grace_period: 60s` para cumprir
  DoD "drena ate 60s") e `HealthzServer` stdlib (`http.server`) em
  thread daemon expondo `GET /healthz -> 200 {"status":"ok"}` para
  Uptime Kuma (INFRA-07). Dockerfile multi-stage com usuario nao-root
  `worker:1002`, `HEALTHCHECK` contra `/healthz`, `STOPSIGNAL
  SIGTERM`, `EXPOSE 8080`. Novas deps em
  `packages/worker-core/pyproject.toml` (run: `sqlalchemy>=2.0`,
  `psycopg[binary]>=3.1`, `redis>=5.0`, `rq>=1.16`; dev:
  `fakeredis>=2.20`). Novo bloco `# Worker RQ (apps/worker -
  API-13)` em `config/.env.example` com `WORKER_HEALTHZ_PORT` e
  `WORKER_DATABASE_URL`. Testes: 10 em `tests/test_crypto_worker.py`
  (round-trip com encrypt da API, tenant errado, versao
  desconhecida, truncamento, tampering, ciphertext nao-bytes,
  tenant_id invalido, KEK ausente em production, KEK base64
  invalida, KEK tamanho errado), 9 em `tests/test_db_nsu.py`
  (get feliz, company missing, cnpj mismatch, cnpj com mascara,
  last_nsu null, UPDATE only-if-greater com filtro SQL correto,
  rejeicao de nsu negativo/bool, noop quando rowcount=0), 13 em
  `tests/test_jobs.py` (sucesso 2 itens, partial com parse_error +
  occurrence PARSE_ERROR, credential decrypt failed -> occurrence
  CRED_INVALID, idempotencia quando INSERT retorna None,
  `fatal_rejected` -> failed + occurrence PORTAL_5XX, storage error
  -> occurrence STORAGE_ERROR, execucao inexistente -> not_found,
  `_decide_final_status` parametrico com 6 ramos), 3 em
  `apps/worker/tests/test_healthz.py` (GET /healthz, 404 em path
  desconhecido, start/stop idempotente) e 9 em
  `apps/worker/tests/test_main.py` (resolvers de env com defaults e
  validacao + `build_worker` com fakeredis + registro de handlers
  SIGTERM/SIGINT). `pytest tests/ --ignore=tests/test_main.py
  --ignore=tests/test_storage.py` = 140 passed; `pytest
  apps/worker/tests/` = 12 passed. DoD E2E (POST /executions ->
  fila -> worker -> items no DB + XML no S3) coberto estruturalmente
  pelos testes unitarios + integracao-ready mas requer
  postgres+redis+B2 reais para rodar end-to-end, validado
  manualmente apos deploy. Move API-13 de "Bloqueadas" (deps
  API-07/CORE-04/CORE-05/API-06 ja mergeadas em main) para "Em
  Andamento" (PR a abrir — Closes #37).
- **API-08** — Listagem/detalhe de executions + execution_items em
  `apps/api/api/executions/routes.py`: novos endpoints `GET /executions`
  (paginado, filtros `company_id`/`status`/`from`/`to` sobre
  `started_at`, ISO 8601 UTC; ORDER `started_at DESC NULLS LAST, id`),
  `GET /executions/{id}/items` (paginado, filtros `status`/`nsu`;
  ORDER `nsu ASC NULLS LAST, id`; 404 antes de listar quando o id
  parent nao existe — RLS isola cross-tenant) e atalho
  `GET /companies/{id}/executions` em
  `apps/api/api/companies/routes.py` (valida 404 da company antes de
  delegar para `query_executions`, helper exportado de
  `executions/routes.py`). `GET /executions/{id}` (entregue por
  API-07) ja cobre "detalhe + contadores agregados" via
  `items_total`/`items_ok`/`items_fail` — sem duplicacao. RBAC: leitura
  liberada para `owner|admin|operator|viewer` (matriz). Schemas novos
  em `apps/api/api/executions/schemas.py`: `ExecutionListOut`,
  `ExecutionItemOut`, `ExecutionItemListOut`, `ExecutionItemStatus`
  (Literal alinhado ao CHECK `ck_execution_items_status` da 0005).
  Migration nova `0017_executions_listing_index.py` cria 2 indices
  para satisfazer o DoD "EXPLAIN usa indice":
  `ix_executions_tenant_started (tenant_id, started_at DESC NULLS
  LAST, id)` (cobre `GET /executions` sem `company_id`) e
  `ix_executions_tenant_status_started (tenant_id, status, started_at
  DESC NULLS LAST)` (cobre `?status=`). O composto ja existente
  `ix_executions_tenant_company_started` (0004) entra quando
  `company_id` esta presente; `ix_execution_items_execution_id` (0005)
  ja serve a listagem de items. 5 testes unitarios novos em
  `tests/test_executions_schemas.py` (envelope lista, item com
  opcionais None, status invalido, Decimal em valor, envelope items
  vazio) + 14 testes de integracao novos em
  `tests/test_executions_routes_integration.py` gated por
  `TEST_DATABASE_URL` (lista feliz com ordenacao por `started_at DESC
  NULLS LAST`, filtro por company/status/periodo, paginacao 5 linhas
  em 3 paginas, isolamento cross-tenant via RLS, viewer pode ler,
  atalho `/companies/{id}/executions` feliz, atalho com company
  inexistente -> 404, atalho cross-tenant -> 404, items feliz com
  ordenacao por nsu, items filtra por status/nsu, items cross-tenant
  -> 404, items viewer pode ler) + 3 testes estaticos da migration em
  `tests/test_migration_0017.py` (importavel, dois indices criados,
  downgrade simetrico). Nova secao "Listagem de executions/
  execution_items — API-08" em `apps/api/README.md` com 3 EXPLAINs
  esperados + receita de validacao manual de paginacao em 10k items.
  Sem mudanca em RBAC matrix (leitura ja era liberada para viewer em
  todas as entradas relacionadas). AST verde em todos os arquivos
  editados; pytest/ruff a cargo do CI
  (PR a abrir — Closes #32).
- **CORE-06** — Smoke test E2E `mtls_session` -> `fetch_nfse` ->
  `S3StorageClient`: novo CLI
  `packages/worker-core/scripts/smoke.py` (executavel via
  `python -m scripts.smoke` a partir do diretorio do pacote) recebe
  PFX A1 por `--pfx`, CNPJ por `--cnpj`, senha **apenas** via env
  `NFSE_PFX_PASSWORD` (jamais via flag — apareceria em `ps`/history e
  ja vinha sendo evitado em CORE-02). Flags adicionais: `--dias`
  (default 7) faz filtro client-side por `data_emissao` no
  `on_progress` (ADN nao aceita filtro por data — pagina por NSU);
  `--max-documentos` impoe teto na paginacao do fetcher;
  `--rate-limit` repassa ao `fetch_nfse`; `--ambiente`
  `PRODUCAO|HOMOLOGACAO` seta `NFSE_AMBIENTE`; `--nsu-inicial`
  permite retomar de um NSU especifico via `InMemoryNsuSource.set`
  (default 0); `--tenant-id`/`--execution-id` aceitam UUID explicito
  ou geram aleatorio para compor `object_key`; `--dry-run` curto-
  circuita o `S3StorageClient` (so conta o que subiria) e e o caminho
  default em ambiente sem `S3_*`; `--verbose` liga `logging.INFO` no
  `worker_core`. Exit codes: `0` ok, `1` uso/config (incluindo
  `NFSE_PFX_PASSWORD` ausente e `S3_BUCKET` ausente sem `--dry-run`),
  `2` falha fatal (`ValueError` do `mtls_session` — PFX/senha/cert),
  `3` rede ou upload (qualquer `Exception` propagada do
  `fetch_nfse`, ou `uploads_failed > 0`). `_make_progress_callback`
  encapsula a logica do callback: `parse_error` -> conta em
  `parse_errors_skipped` e nao sobe; `data_emissao` fora da janela
  (`< today - dias`) -> conta em `filtered_by_date` e nao sobe; data
  ausente/invalida -> mantem (decisao conservadora — prefere subir
  XML legitimo a descartar silenciosamente); item ok dentro da
  janela -> chama `S3StorageClient.upload_xml(tenant_id,
  execution_id, item.nsu, item.xml_bytes)` e acumula
  `object_key`/`sha256`/`size` em `_UploadCounters` (lista de
  `object_keys` e amostrada nos 3 primeiros no resumo final).
  `_emit_log` imprime cada evento (`smoke.start`, `fetch_start`,
  `fetch_complete`, `smoke.upload_ok`, `smoke.upload_failed`,
  `smoke.dry_run.would_upload`, `smoke.skip_parse_error`,
  `smoke.skip_no_xml`, `item_parse_error`, `callback_error`,
  `fatal_error`) como JSON em uma linha (`json.dumps(...,
  ensure_ascii=False, default=str)`) e **filtra explicitamente**
  qualquer chave `pfx_password`/`pfx_bytes` que tente passar pelo
  payload — defesa em profundidade alem do que o
  `worker_core.collector.fetch_nfse` ja sanitiza. Resumo final
  (legivel) imprime `cnpj`/`cutoff`/`nsu_from`/`nsu_to`/contadores do
  `FetchSummary` + contadores do smoke + amostra de `object_keys`.
  No `finally` do `main`, `pfx_bytes` e `password` sao reescritos
  para vazio (best-effort — Python nao expoe zeragem de paginas, mas
  evita reuso acidental no escopo). README do pacote ganha secao
  "Smoke test E2E (CORE-06)" com bloco de envs (dry-run e real),
  recomendacao de `--max-documentos 50` na primeira rodada e
  alerta explicito "NUNCA commite `.pfx`, senha ou chaves S3". Testes
  novos em `tests/test_smoke.py` (13 casos): `_within_window` (3 —
  data dentro/fora da janela e fallback conservador para data
  invalida/ausente/ISO); `_parse_args`/`_validate_args` (5 —
  defaults minimos, CNPJ nao-14-digitos, PFX inexistente, `--dias 0`,
  `--tenant-id` UUID invalido); `main` sem `NFSE_PFX_PASSWORD` ->
  `EXIT_USAGE` + mensagem em stderr; `_emit_log` filtra
  `pfx_password`/`pfx_bytes` mesmo se passados; `_make_progress_callback`
  filtra por data sem chamar storage, dry-run conta sem tocar storage
  e `parse_error` e pulado. Modulo carregado via `importlib.util`
  registrando em `sys.modules` (necessario para `dataclasses` resolver
  o tipo do `_UploadCounters`). `pytest tests/
  --ignore=tests/test_main.py` = 151 passed (138 anteriores + 13
  novos). Sem dependencias novas — script usa apenas stdlib +
  `worker_core` (`InMemoryNsuSource`, `fetch_nfse`, `S3StorageClient`,
  `S3Settings`, `StorageError`, `NfseItem`, `FetchSummary`). DoD do
  ticket itens 1 e 2 ("smoke rodado com 1 CNPJ real" + "XML aparece
  no bucket com object key correto") permanece a cargo do owner apos
  setup manual do bucket B2 (issue #8) e disponibilidade de PFX A1
  real — o caminho feliz local foi exercitado pela suite de testes
  via mocks (CORE-04 fetcher + CORE-05 moto.mock_aws), e o `--dry-run`
  permite validar o fluxo offline. Move CORE-06 para "Em Andamento"
  (todas as dependencias CORE-02..05 ja em "Concluidos")
  (PR a abrir — Closes #24).

- **INFRA-08** — Backup diario do Postgres para S3: script
  `infra/scripts/backup-postgres.sh` executa `pg_dump -Fc -Z 9` dentro
  do container do Postgres (INFRA-05) via `docker compose exec -T`
  (evita instalar `postgresql-client` no host), classifica o dump em
  `daily/YYYY-MM-DD.dump` nos dias 2-31 e `monthly/YYYY-MM.dump` no dia
  1, cifra opcionalmente com `age` (default ON em staging/prod, chave
  publica em `BACKUP_AGE_RECIPIENT` e privada apenas no cofre do
  owner), faz upload para `s3://$S3_BUCKET/backups/postgres/<kind>/`
  via `aws s3 cp`, limpa dumps locais com
  `find -mtime +$BACKUP_RETENTION_LOCAL_DAYS -delete` (default 3d) e
  registra 1 linha JSON por execucao em
  `/srv/nfse/<env>/logs/backup-postgres.log` (status/size/duration/sha256).
  Script `infra/scripts/restore-postgres.sh` aceita `--latest` ou
  `--key <s3-key>` + `--target-db <nome>` para drill isolado, decifra
  age se necessario (`BACKUP_AGE_IDENTITY` aponta para a privada
  temporaria), cria DB alvo se nao existir, faz
  `pg_restore --clean --if-exists --no-owner --no-privileges` e imprime
  checksum de sanidade (`count(*)` em `tenants`/`users`/`tenant_users`/
  `companies`/`audit_logs`). Systemd template
  `infra/systemd/nfse-backup-postgres@.{service,timer}` (instancia com
  `@prod`/`@staging`) dispara `OnCalendar=*-*-* 03:00:00` no TZ do host
  (`America/Sao_Paulo` por INFRA-01), `Persistent=true`,
  `RandomizedDelaySec=5min`, `EnvironmentFile=/srv/nfse/%i/config/.env`,
  `User=deploy`, hardening basico (`NoNewPrivileges`,
  `ProtectSystem=full`). Lifecycle do bucket B2 ganha 2 regras em
  `infra/s3-lifecycle.json`: `backups/postgres/daily/` -> 30d e
  `backups/postgres/monthly/` -> 365d (separacao por prefix porque B2
  nao suporta lifecycle por tag — mesmo workaround que
  `tenants-exports/` em INFRA-06); total passa de 2 para 4 rules no
  bucket. Novo bloco `# Backup Postgres (INFRA-08)` em
  `config/.env.example` com `BACKUP_LOCAL_DIR`, `BACKUP_S3_PREFIX`,
  `BACKUP_RETENTION_LOCAL_DAYS`, `BACKUP_LOG_FILE`, `BACKUP_ENCRYPT`,
  `BACKUP_AGE_RECIPIENT` e `BACKUP_AGE_IDENTITY`. Runbook completo em
  `infra/backup.md` cobrindo instalacao (pre-requisitos + geracao do
  par age + symlinks + `systemctl enable --now`), uso manual, aplicacao
  das 2 novas rules via B2 CLI/console, drill de restore em staging
  passo-a-passo (copia da chave privada para `/tmp`, `--target-db
  nfse_restore_drill`, validacao com `md5(string_agg(...))`, cleanup
  com `shred -u`), matriz de troubleshooting e checklist do DoD. Sem
  execucao real possivel neste PR — DoD manual do owner (backup roda
  por 2 dias seguidos + drill de restore em staging) valida apos
  provisionamento na VPS e aplicacao das lifecycle rules (rastreio
  segue em #10 ate validacao, mesmo padrao de INFRA-04/07/09).
  `bash -n` e `systemd-analyze verify` verdes localmente
  (PR a abrir — Closes #10).

- **API-09** — Inbox de ocorrencias operacionais em
  `apps/api/api/occurrences/`: `GET /occurrences` paginado com filtros
  `status`/`severity`/`company_id`, `GET /occurrences/{id}`,
  `POST /occurrences/{id}/acknowledge` (`open` -> `ack`, idempotente
  em `ack`, 409 em `resolved`/`ignored`),
  `POST /occurrences/{id}/resolve` (qualquer aberto -> `resolved`,
  grava `resolved_at = now()`, exige `note` no body — 422 sem nota,
  registrada em `audit_logs.metadata.note`),
  `POST /occurrences/{id}/assign` (valida membership do tenant via
  `tenant_users`; user de outro tenant ou inexistente -> 404). RBAC
  pela matriz: leitura para todos os papeis, acoes mutadoras para
  `owner|admin|operator` (viewer -> 403). Cada mutacao insere
  `audit_logs` com `action='occurrence.<verb>'`,
  `resource_type='occurrence'` e metadata publico (status_from/to,
  note, assignee_user_id, previous_assignee_user_id) — `tenant_id`
  injetado pela GUC `app.current_tenant`. Schemas em
  `apps/api/api/occurrences/schemas.py` (`OccurrenceOut`/
  `OccurrenceListOut`/`OccurrenceResolveIn` com
  `note: str (1..2000) + extra='forbid'`/`OccurrenceAssignIn`). Router
  registrado em `apps/api/api/main.py`. Catalogo canonico de codigos
  em `docs/architecture/occurrence-codes.md` (CERT_EXPIRED,
  CERT_EXPIRING, CERT_REVOKED, CRED_INVALID, PORTAL_5XX,
  PORTAL_TIMEOUT, RATE_LIMIT, REPROCESS_NEEDED, PARSE_ERROR,
  STORAGE_ERROR, UNKNOWN — com severity_default e link para o
  runbook). Matriz RBAC atualizada em
  `docs/architecture/rbac-matrix.md` com a nova secao "Occurrences
  (inbox operacional)". Testes: `tests/test_occurrences_schemas.py`
  (11 unitarios — note vazia/teto/extra=forbid, UUID invalido,
  severity/status validos no `Out`) +
  `tests/test_occurrences_routes_integration.py` (22 casos gated por
  `TEST_DATABASE_URL` — lista/filtros/paginacao, detalhe + 404
  cross-tenant via RLS, viewer -> 403, operator pode mudar,
  acknowledge feliz com audit, idempotencia em ja-`ack`, 409 em
  resolved/ignored, resolve grava `resolved_at` + audit com nota,
  resolve sem nota -> 422, resolve em `ignored` -> 409, assign feliz,
  user de outro tenant -> 404, reassign registra
  `previous_assignee_user_id`, 401 sem token, OpenAPI lista os 5
  endpoints). `pytest tests/ --ignore=tests/test_rbac.py`: 139 passed
  + 83 skipped. Move API-09 de "Bloqueadas" para "Em Andamento" —
  DATA-04 (dependencia) ja concluida
  (PR a abrir — Closes #33).
- **APP-03** — `/empresas` lista + detalhe (abas). Lista em
  `apps/web-app/app/empresas/page.tsx` + `EmpresasView`/`EmpresasTable`
  consumindo `<DataTable>` (DS-06) com filtros server-side `status`
  (select 3-valores) e `uf` (text 2 letras), colunas
  `cnpj/razao_social/uf/status (StatusBadge)/last_success_at/created_at`,
  link no CNPJ -> `/empresas/[id]`, export CSV, `enableSorting=false`
  porque API-05 ainda nao suporta `?sort=`. Filtro "ultimo sucesso" do
  ticket fica como **coluna informativa apenas** (API-05 nao filtra por
  `last_success_at`; comentario inline + nota no PR sugerindo extender o
  endpoint num ticket futuro). Botao "Nova empresa" visivel para
  `owner|admin|operator` abre `NovaEmpresaDialog` (modal sem Radix em
  novo `components/ui/modal.tsx`, com focus trap, Esc/clique no backdrop
  e bloqueio de scroll do body) com form react-hook-form + zod usando
  `CNPJInput` (DS-07), select de UF (27 siglas) e codigo IBGE; tras
  `409 -> mensagem clara` (CNPJ duplicado ou limite do plano), `403 ->
  "sem permissao"` e em sucesso invalida o cache react-query
  `[empresas:list]`. Detalhe `apps/web-app/app/empresas/[id]/page.tsx`
  -> `CompanyDetailView` (header com CNPJ formatado + razao social +
  StatusBadge) + `CompanyTabs` controlado por `?tab=...`, `role=tablist`/
  `role=tab` com `aria-selected`/`aria-controls`/`tabIndex` corretos e
  navegacao por teclado (Setas/Home/End). Cada painel e
  `React.lazy(import(...))` com `Suspense` fallback — **prova de DoD
  "abas carregam sob demanda"**: `data-tab-panel` de aba nao visitada
  permanece vazio (validado em `company-tabs.test.tsx`). 6 paineis em
  `app/empresas/[id]/tabs/`: `overview-tab.tsx` (dados cadastrais,
  cards "ultima coleta com sucesso"/"proxima execucao agendada", botoes
  Editar/Excluir gated por papel — Editar para `owner|admin|operator`,
  Excluir para `owner|admin` — abrindo dialogs proprios que invalidam
  os caches `[empresas:list]` e `[empresas:detail, id]` em sucesso e
  redirecionam para `/empresas` apos delete) + 5 stubs informativos
  (`executions-tab` -> APP-05/API-07, `credential-tab` -> APP-04
  citando que o backend API-06 ja existe, `schedules-tab` -> APP-08/
  API-09, `files-tab` -> APP-07/API-10 com nota da retencao 90d
  ADR-003, `occurrences-tab` -> APP-06 com link DOCS-03/04). Cliente
  HTTP novo em `apps/web-app/lib/api/companies.ts`
  (`buildListQuery`/`listCompanies`/`getCompany`/`createCompany`/
  `updateCompany`/`deleteCompany` reaproveitando `apiFetch` da APP-01
  com `accessToken` + `onTokenRefreshed`; mapeia pageIndex 0-based ->
  page 1-based, normaliza UF para uppercase, `extra=forbid` do PATCH
  honrado pelo tipo `CompanyUpdatePayload`; helpers `formatCnpj` e
  `COMPANY_STATUS_LABEL`). Item "Empresas" adicionado em
  `components/app-shell/nav-items.ts` (substitui o placeholder
  "Tenants" — rota `/empresas` real, fica destacado em todo
  `/empresas/*` pelo `pathname.startsWith` ja existente no Sidebar).
  20 testes vitest novos: `lib/api/companies.test.ts` (14 — query
  string, header Authorization, propagacao de ApiError 403/404, PATCH
  com campos parciais, DELETE 204 sem lancar, `formatCnpj`),
  `app/empresas/empresas-view.test.tsx` (2 — viewer nao ve botao,
  owner/admin/operator veem) e `app/empresas/[id]/company-tabs.test.tsx`
  (4 — 6 abas com role=tab, so "overview" monta no default,
  `data-tab-panel="credential"` continua vazio antes do clique, setas
  navegam). Typecheck verde, `next lint` zero warnings, `vitest run`
  142 passed (122 existentes + 20 novos)
  (PR a abrir — Closes #51).
- **API-12** — CRUD `/schedules` (agendamentos cron + TZ): pacote
  `apps/api/api/schedules/` com `cron.py` (valida cron 5-campos via
  `croniter` rejeitando 6/7, valida TZ IANA via `zoneinfo.ZoneInfo`,
  `compute_next_run` roda na TZ local e persiste em UTC), `presets.py`
  (3 sugestoes: diario 03:00, semanal seg 06:00, mensal dia 1 05:00),
  `schemas.py` (`ScheduleIn`/`ScheduleUpdate`/`ScheduleOut` com
  `extra=forbid` protegendo `last_run_at`/`next_run_at`/etc como
  read-only) e `routes.py` com `GET /schedules` paginado (filtros
  `enabled`/`company_id`), `GET /{id}`, `GET /schedules/presets`,
  `POST` (RBAC owner|admin|operator; valida cron+TZ com fallback
  explicito para 400; valida company existente via RLS; calcula
  `next_run_at` se `enabled=true`; grava `created_by_user_id`),
  `PATCH` (recomputa `next_run_at` quando `cron_expr`/`timezone` mudam
  ou `enabled` vira true; limpa quando vira false; `extra=forbid` ->
  422 em tentativa de tocar read-only), `DELETE` hard (owner|admin).
  Router registrado em `api/main.py`; matriz em
  `docs/architecture/rbac-matrix.md` ganha secao Schedules. Nova dep
  `croniter>=2.0` em `apps/api/pyproject.toml`. 31 unit tests de cron
  (`test_schedules_cron.py` — 5-campos, rejeicao 6/7, sintaxe, TZ,
  calculo em UTC para os 3 presets e cross-TZ) + 10 unit tests de
  schemas (`test_schedules_schemas.py` — defaults, cron/TZ invalidos,
  `extra=forbid`, PATCH parcial) + 18 integracao
  (`test_schedules_routes_integration.py`, gated `TEST_DATABASE_URL`)
  cobrindo CRUD feliz tenant-wide e company-scoped, `next_run_at`
  coerente (hora UTC da primeira execucao), pause/resume limpa/recalcula,
  cron/TZ invalidos -> 400/422 com mensagem clara, cross-tenant 404,
  company de outro tenant 400, RBAC (viewer -> 403, operator -> 403
  no DELETE), PATCH vazio 400, DELETE idempotente, presets com 3 itens,
  filtros por `enabled`/`company_id`. `pytest apps/api`: 204 passed +
  86 skipped, 0 falhas (PR a abrir — Closes #36).

- **API-11** — `/files` (listar + URL pre-assinada 1h): novo pacote
  `apps/api/api/files/` com `routes.py` (`GET /files` paginado com
  filtros `kind`/`company`/`from`/`to`; `GET /files/{id}/url` gera
  presigned 3600s) e `schemas.py` (`FileKind`, `FileOut`, `FileListOut`,
  `FileUrlOut`). Novo helper `generate_presigned_get_url` em
  `apps/api/api/storage.py` (usa `boto3.generate_presigned_url` com
  `ExpiresIn=3600` fixo; TTL exposto como argumento mas clampado em
  0 < s <= 7d). Filtro por `company` usa JOIN em `executions` via
  `files.source_execution_id` — files sem execution nao aparecem
  quando o filtro e usado (comportamento desejado). RBAC: leitura e
  geracao de URL liberadas para todos os papeis (viewer incluido),
  alinhado com a linha "Download de XLSX / artefatos" da matriz.
  Cross-tenant cai naturalmente em 404 via RLS de `files` (policy
  `files_isolation` da migration `0011_files`). Audit log
  `file.download_url` grava metadata publica (`file_id`, `kind`,
  `object_key`, `bytes`, `expires_in`) e **nunca** a URL em si — a
  URL assinada e credencial temporaria. Router registrado em
  `apps/api/api/main.py`. 4 unit tests em
  `apps/api/tests/test_storage_presigned.py` (URL contem
  `X-Amz-Signature`/`X-Amz-Expires=3600`, default 1h, rejeita key
  vazia, rejeita TTL invalido) + 12 integracao gated por
  `TEST_DATABASE_URL` + moto em
  `apps/api/tests/test_files_routes_integration.py` (isolamento por
  tenant, filtros kind/company/periodo, paginacao, viewer consegue
  ler, URL tem `expires_in=3600`, cross-tenant -> 404, audit grava
  sem vazar URL, 404 para id inexistente, viewer consegue gerar URL).
  `pytest apps/api`: 153 passed + 79 skipped (todos os testes novos
  de unit passam). Sem migration nova. DoD manual "URL funciona no
  navegador" valida apos setup do bucket B2 real pelo owner (rastreio
  em #8) — moto nao serve HTTP, apenas assina URL estruturalmente
  (PR a abrir — Closes #35).

- **API-07** — `POST /executions` + `GET /executions/{id}` em
  `apps/api/api/executions/` (router + schemas). Cria 1 linha em
  `executions` por company e enfileira `worker_core.jobs.run_execution`
  (via string — worker resolve o import no pick) numa fila RQ
  configurada por `API_REDIS_URL` + `API_QUEUE_NAME`. Novo
  `apps/api/api/queue.py` expoe `get_redis_client()`, `get_queue()`,
  `ping_redis()`, `enqueue_run_execution(execution_id, *, tenant_id,
  dry_run)` (dry_run vai apenas no `meta` do job — nao persiste no
  schema) e `QueueError` agnostico. `POST`: RBAC
  `owner|admin|operator`; valida companies (RLS) em `companies` +
  credencial ativa com `cert_not_after > now()` em
  `company_credentials` — companies faltantes ou sem credencial
  rejeitam em bloco com 422; pre-pinga Redis antes do INSERT (502
  sem tocar DB quando offline); se o enqueue estourar apos o INSERT,
  marca a linha como `failed` com `error_summary='enqueue_failed'`
  e `finished_at=now()`, devolve `job_id=null`/`enqueue_error` no
  item correspondente da resposta. `GET`: RBAC irrestrito (viewer
  inclusive), 404 cross-tenant via RLS, devolve contadores,
  periodo, NSU, `triggered_by_user_id`. Trigger default `manual`
  (dominio alinhado com CHECK `ck_executions_trigger` do 0004).
  Novas deps run `redis>=5.0` + `rq>=1.16` em
  `apps/api/pyproject.toml`; dev `fakeredis>=2.20`. Novo bloco
  `# Fila Redis para execucoes (API-07)` em `config/.env.example`
  com `API_REDIS_URL=redis://localhost:6379/0` + `API_QUEUE_NAME=
  nfse-executions`. 12 testes unitarios em
  `apps/api/tests/test_executions_schemas.py` (defaults, trigger
  dominio, `period_end >= period_start`, deduplicacao de
  `company_ids`, `min_length/max_length`, `extra='forbid'`, envelope
  de resposta) + 7 em `apps/api/tests/test_queue_unit.py`
  (fakeredis + RQ: ping, enqueue feliz, meta/args/func_name
  corretos, dry_run default, acumulo na fila, QueueError em ping e
  enqueue com Redis quebrado, QueueError sem URL) + 10 de
  integracao em `apps/api/tests/test_executions_routes_integration.py`
  gated por `TEST_DATABASE_URL` + fakeredis (caminho feliz com N=2
  -> N executions + N jobs com args batendo, dry_run=True propaga
  meta, GET cross-tenant -> 404, company alheia -> 422
  `companies_not_found`, company sem credencial -> 422
  `credential_missing_or_expired`, credencial vencida -> 422,
  `period_end < period_start` -> 422 Pydantic, viewer -> 403 no
  POST mas 200 no GET, operator pode disparar, Redis down antes do
  INSERT -> 502 sem tocar DB, enqueue falha no meio -> 1 queued +
  1 failed com audit correto). `ruff check apps/api/` verde,
  `pytest apps/api` = 178 passed + 72 skipped (PR a abrir —
  Closes #31).

- **APP-10** — Pagina `/assinatura` (placeholder sem gateway, ADR-004):
  rota `apps/web-app/app/dashboard/assinatura/page.tsx` (server
  component) renderiza plano atribuido + status via `<StatusBadge>`,
  tres `<UsageMeter>` (CNPJs, Execucoes no mes, Usuarios) com
  contador `used/limit`, percentual, `role="progressbar"` e tom
  ok/warn/full (>=80% warn, 100% full — usuarios 5/5 no mock), callout
  "Para alterar plano, entre em contato com o suporte" com botoes
  WhatsApp + email (placeholders ate SITE-* destravar nome comercial)
  e secao "Historico de faturas" vazia. **Sem** botao de upgrade —
  cobranca manual reforcada (ADR-004). Dados de teste isolados em
  `apps/web-app/lib/subscription/mock.ts` (`SubscriptionSnapshot` com
  shape alinhado a `plans.limits` do seed DATA-07 e `plans.code`
  tipado como `starter|pro|scale`) para que um endpoint futuro troque
  a funcao `getSubscriptionSnapshot()` sem tocar no layout. Novo item
  `Assinatura` (icone `CreditCard`) em
  `apps/web-app/components/app-shell/nav-items.ts`. Componente novo
  reutilizavel `apps/web-app/components/subscription/usage-meter.tsx`
  (`title` + `metric: SubscriptionMetric` + `icon: LucideIcon`,
  preserva `data-tone="ok|warn|full"`, `aria-valuenow={used}`,
  `aria-valuemin=0`, `aria-valuemax={limit}`, `aria-label` por card,
  clampa largura da barra em 100% quando `used > limit`, lida com
  `limit=0` sem divisao por zero) extrai o `UsageCard` que antes
  estava inline na page. Spec vitest
  `app/dashboard/assinatura/page.test.tsx` (6 casos) preservada:
  render do plano + badge `Ativo`, tres cards com `used/limit` +
  progressbar, card de usuarios marcado `data-tone="full"` com 5/5,
  mensagem de suporte + links `wa.me`/`mailto`, ausencia defensiva de
  botoes/links "upgrade|fazer upgrade|assinar|mudar plano" (prova do
  DoD) e placeholder vazio de faturas. Spec nova
  `components/subscription/usage-meter.test.tsx` (7 casos) cobre
  contrato do componente em isolado: titulo + `used/limit` + `(%)`,
  `aria-valuenow/min/max` apontando para `used/limit`, thresholds
  ok/warn(>=80%)/full(100%), clamp em 100% para `used>limit` e
  tratamento de `limit=0` (`tone=ok`, label "(-)"). `tsc --noEmit`,
  `next lint` e `vitest run` = 135 testes verdes em 13 arquivos
  (PR a abrir — Closes #58).

- **APP-09** — `/usuarios` + convites: pagina
  `apps/web-app/app/usuarios/` (layout com `RequireAuth` + `AppShell`)
  lista membros (nome, email, papel, status, ultimo login) com menu de
  acoes por linha (alterar papel, remover) e secao separada de
  convites pendentes. Camada `apps/web-app/lib/users/` com
  `types.ts` (`Member`, `Invitation`, `Role`), `schemas.ts` (zod de
  invite/update/accept + helper `rolesAssignableBy`), `api-client.ts`
  (`listMembers`/`listInvitations`/`inviteMember`/`revokeInvitation`/
  `updateMemberRole`/`removeMember`/`acceptInvitation` via `apiFetch`
  do APP-01 + novo Route Handler `app/api/auth/accept-invitation/`
  que grava o cookie httpOnly de refresh) e `rbac.ts` com guardas
  `canRemoveMember`/`canChangeRole`/`canInviteWithRole`/
  `canRevokeInvitation` alinhados a `docs/architecture/rbac-matrix.md`
  (admin so atribui operator/viewer; owner e protegido). Componentes
  em `apps/web-app/components/users/` — `Modal` + `ConfirmDialog`
  leves (sem Radix, padrao do AppShell), `RoleSelect` (reage ao papel
  do ator), `RoleBadge`, `InviteDialog` (react-hook-form + zod),
  `MembersTable` (menu de acoes desabilitado quando o ator nao pode
  agir, incluindo "nao gerenciar a si mesmo") e `PendingInvitations`
  (revogar com confirmacao; oculta accepted/revoked/expired).
  `/aceitar-convite/[token]` deixa de ser stub: chama
  `POST /api/auth/accept-invitation`, aplica sessao e redireciona
  para `/dashboard`. Sidebar (`components/app-shell/nav-items.ts`)
  ganha item "Usuarios" apontando para `/usuarios`. Testes vitest:
  `lib/users/rbac.test.ts` (16 casos cobrindo toda a matriz,
  incluindo DoD "admin nao rebaixa owner"), `lib/users/schemas.test.ts`
  (11 casos), `components/users/invite-dialog.test.tsx` (5 casos —
  submissao, validacao de email, restricao de papel para admin, erro
  da API), `components/users/members-table.test.tsx` (6 casos —
  vazio, listagem, admin+owner desabilitado, auto-gestao bloqueada,
  remover e alterar papel) e `components/users/pending-invitations.test.tsx`
  (4 casos — lista vazia, revogar, erro+retry, viewer desabilitado).
  E2E Playwright `apps/web-app/e2e/usuarios.spec.ts` intercepta
  `/tenant/*` + `/api/auth/accept-invitation` e cobre convite feliz +
  aceite redirecionando pro dashboard + admin vendo owner bloqueado.
  `pnpm -C apps/web-app typecheck/lint/test` verdes (164 specs no
  total, +42 novos). Backend (`GET/POST /tenant/members`,
  `/tenant/invitations`, `/tenant/invitations/{id}/revoke` e
  `/tenant/invitations/accept`) sera entregue em **ticket API
  futuro** — mesmo padrao do APP-01 (`/recuperar-senha`,
  `/redefinir-senha`), onde a UI e o contrato ficam prontos antes do
  handler (PR a abrir — Closes #57).
- **DS-07** — Inputs especiais de formulario (FileDropzone,
  SecretField, CNPJInput, PeriodPicker) em
  `apps/web-app/components/ui/` (PR a abrir — Closes #46).
- **API-06** — Upload `/companies/{id}/credential` com cifra
  AES-256-GCM por tenant: novo `apps/api/api/crypto.py` (envelope
  encryption KEK -> HKDF-SHA256 -> DEK por tenant; ciphertext = `\x01`
  + nonce(12B) + GCM ct+tag, AAD = bytes do `tenant_id`); novo
  `apps/api/api/storage.py` (boto3 S3-compat, `put`/`get`/`delete`
  sob prefix dedicado `S3_CREDENTIALS_PREFIX=tenants-credentials/`,
  **sem lifecycle** — credencial e viva); router em
  `apps/api/api/companies/credentials.py` (POST multipart `pfx`+
  `password` para `owner|admin`, parseia PKCS#12, extrai
  fingerprint/validade/CN, valida CN vs CNPJ com warn em mismatch,
  cifra senha + PFX, INSERE em `company_credentials` revogando ativas
  anteriores na mesma transacao, PUT no S3 com rollback em falha,
  audit_log `credential.upload` sem segredo; DELETE marca status
  `revoked`, remove blob best-effort, audita `credential.revoke`).
  Settings novas: `API_CREDENTIAL_KEK_B64` (obrigatorio em
  staging/prod via `model_validator`), `API_CREDENTIAL_MAX_PFX_BYTES`
  (default 1 MiB) e `S3_CREDENTIALS_PREFIX`. Runbook
  `infra/s3-bucket.md` atualizado: layout passa a expor
  `tenants-credentials/` sem rule de TTL e Application Key precisa
  cobrir os 3 prefixos (ou key dedicada por prefix). Deps novas:
  `cryptography>=42`, `boto3>=1.34`, `python-multipart>=0.0.9` (run)
  + `moto[s3]>=5.0` (dev). 14 testes unitarios novos
  (`test_crypto.py` cobre round-trip, AAD, tampering, KEK
  ausente/invalida; `test_storage_credentials.py` cobre layout de
  chave, round-trip via moto e `StorageError` em bucket inexistente)
  + suite de integracao `test_credentials_routes_integration.py`
  (gated `TEST_DATABASE_URL` + `moto`) cobrindo upload feliz com
  audit, decifragem ponta-a-ponta abrindo o PFX (DoD "worker decifra
  e usa"), senha errada -> 400, PFX > teto -> 413, cross-tenant ->
  404, viewer -> 403, revogacao limpa o blob e re-upload revoga o
  anterior, mais ajuste cirurgico em `test_seed.py` para tambem setar
  `API_CREDENTIAL_KEK_B64` ao testar abort em production. `pytest`
  local: 163 passed + 68 skipped. Execucao do DoD manual (criar 3a
  Application Key ou rever a existente para enxergar
  `tenants-credentials/`) fica para o owner — sem isso, o PUT real
  contra B2 retorna 401; o smoke test esta documentado no runbook
  (PR a abrir — Closes #30).
- **APP-04** — Aba "Credencial" em
  `/dashboard/empresas/[id]/credencial` (apps/web-app): painel com
  `<StatusBadge>` + fingerprint SHA-256 (formato OpenSSL `aa:bb:..`)
  + validade em pt-BR, botao "Atualizar credencial" abrindo dialog
  com `<FileDropzone>` (.pfx/.p12 ate 1 MiB) + `<SecretField>`
  (senha PFX), "Revogar" via ConfirmDialog "digite REVOGAR" e
  "Testar agora" desabilitado (aguardando endpoint dedicado de
  handshake — issue a abrir). Erros 400/413/502/403 traduzidos
  para feedback acionavel em portugues ("senha incorreta ou PFX
  invalido", "arquivo excede limite de 1 MiB", "falha ao gravar
  no storage", "voce nao tem permissao"); badge vira
  `cert_expiring` nos ultimos 30 dias, `failed` apos a validade,
  `blocked` em revogada, `cred_invalid` em invalida.
  Incluidos no escopo: (a) GET minimo
  `/companies/{id}/credential` na API (RBAC leitura = todos os
  papeis; devolve a credencial `active` mais recente ou 404; nunca
  expoe ciphertext/senha; `cn_matches_cnpj` volta como `None`
  porque o CN nao e persistido); (b) novo `components/ui/dialog.tsx`
  (modal acessivel sem Radix, focus trap, Esc, overlay click);
  (c) `lib/companies/credentials.ts` com cliente tipado + mapeador
  de erros + `formatFingerprint` + `decideCredentialBadge`.
  37 testes novos no apps/web-app (credentials helpers, status
  block, upload dialog, revoke dialog e panel orquestrando estado
  de auth) + 4 testes de integracao no apps/api cobrindo GET feliz
  pos-upload sem ciphertext, GET 404 pre-upload, GET 404 apos
  revoke (so retorna active) e GET RBAC permitindo viewer.
  `pytest apps/api` = 163 passed + 72 skipped; `pnpm --filter
  web-app test` = 164 passed; `pnpm typecheck` e `pnpm lint`
  verdes; `ruff check apps/api` limpo
  (PR a abrir — Closes #52).

- **API-15** — Export ZIP assincrono (autor: Claude; 2026-04-16).
  Nova tabela `exports` via migration `0017_exports.py` (colunas
  `kind`, `period_start/end`, `status IN ('queued','running','ready',
  'failed','empty')`, `file_id` FK para `files.id`, contadores,
  `error_code`/`error_message`, timestamps) + RLS + 3 indices
  (`tenant_created`, `tenant_company`, parcial `inflight` em
  `(queued,running)`) + GRANTs DML para `app_user` + downgrade
  completo. CHECK do `kind` hoje cobre apenas `zip_xml` —
  `excel_consolidated` (previsto no ticket) foi deliberadamente
  adiado para nao expor caminho morto na API; extensao do enum vira
  migration futura no ticket do consolidado. Novo modulo
  `apps/api/api/exports/`: `schemas.py` (`CreateExportIn` com
  `extra='forbid'` + validator `period_end >= period_start`,
  `CreateExportOut` com `export_id/status/job_id/enqueue_error`,
  `ExportOut` incluindo `download_url` + `expires_in` preenchidos
  **so** quando `status='ready'` + `file_id` populado) e
  `routes.py`: `POST /exports` (RBAC `owner|admin|operator`)
  valida company via RLS, pre-pinga Redis (502 sem tocar DB),
  insere em `queued`, enfileira `worker_core.jobs.build_export` por
  string (RQ; job_timeout=2h, meta com `tenant_id`); em enqueue-fail
  pos-INSERT marca `failed`/`error_code='enqueue_failed'` e devolve
  `job_id=null`. `GET /exports/{id}` libera para todos os papeis
  (viewer incluido), faz LEFT JOIN em `files` e, se `ready`, gera
  URL pre-assinada 1h via `generate_presigned_get_url` (reusa helper
  API-11), grava audit `export.download_url` em `audit_logs` com
  metadata publica (`export_id`, `file_id`, `object_key`, `bytes`,
  `expires_in`) — a URL em si jamais e logada/persistida. Router
  registrado em `apps/api/api/main.py`. Matriz em
  `docs/architecture/rbac-matrix.md` ganha secao "Exports (ZIP
  assincrono)". Worker: novo `packages/worker-core/worker_core/
  jobs.py` com `build_export(export_id)` — entrypoint RQ sem
  dependencia de `apps/api` (usa `psycopg` direto + envs
  `WORKER_DATABASE_URL`/fallback `API_DATABASE_URL`). Fluxo:
  (1) carrega `exports`, valida kind/status e marca `running` com
  `started_at=now()`; (2) lista `execution_items.status='ok'` com
  `xml_object_key` do tenant/company no periodo filtrando por
  `data_emissao`; (3) se vazio -> `status='empty'` sem criar artefato;
  (4) cria ZIP em tmpfs (`EXPORT_TMPFS_DIR` default `/dev/shm` com
  fallback `tempfile.gettempdir()`), baixa cada XML via novo metodo
  `S3StorageClient.download_bytes` (com mesma politica de retry do
  PUT — tenacity 4 tentativas, backoff 0.5..8s em erros transientes)
  e escreve `{nsu}.xml` no ZIP com `ZIP_DEFLATED`; (5) se bytes
  acumulados excedem `EXPORT_MAX_BYTES` (default 2 GiB, DoD do
  ticket), levanta `ExportError('size_limit_exceeded')` e a linha
  vai para `failed` sem criar `file`; (6) sucesso -> `upload_export`
  gera object_key canonico `tenants-exports/{tid}/{file_id}.zip`,
  inserimos `files` com `id` **explicito** (mesmo UUID usado no
  object_key para manter chave consistente), `kind='export'`,
  `bytes=upload.size`, `checksum_sha256=upload.sha256` e
  `expires_at=now()+30d` (menor que o default 90d do ADR-003 porque
  export e artefato derivado); (7) marca `exports.status='ready'`
  com `file_id`, `items_count`, `total_bytes`, `finished_at=now()`;
  (8) enfileira 2 linhas em `notifications` (`channel='inapp'` +
  `channel='email'`, `type='export.ready'`, payload
  `{export_id,file_id,kind}`, `status='pending'`). Delivery real
  (SMTP / push) fica para ticket futuro seguindo o mesmo padrao do
  APP-09 (UI/contrato prontos antes do handler). Codigos de erro
  canonicos: `size_limit_exceeded`, `db_error`, `s3_error`,
  `kind_not_implemented`, `unexpected`. Tmpfs e sempre limpo no
  `finally` mesmo em erro. Idempotencia: job re-picado em `ready`/
  `failed`/`empty` sai com `reason='already_finalized'` sem reabrir.
  Novas envs em `config/.env.example` no bloco `# Export ZIP
  assincrono (API-15)`: `WORKER_DATABASE_URL`, `EXPORT_TMPFS_DIR=
  /dev/shm`, `EXPORT_MAX_BYTES=2147483648`. Testes novos: 8 unit em
  `apps/api/tests/test_exports_schemas.py` (defaults, extra=forbid,
  period invalido, `same_day_ok`, `kind` so aceita `zip_xml` hoje,
  envelope de resposta, `ExportOut` obriga campos), 4 estaticos em
  `apps/api/tests/test_migration_0017.py` (revision/down_revision,
  colunas, CHECKs, RLS+GUC, grants, downgrade simetrico, indice
  parcial `inflight`), 12 integracao em `apps/api/tests/
  test_exports_routes_integration.py` (gated `TEST_DATABASE_URL` +
  fakeredis + moto: POST feliz + job enfileirado, viewer 403,
  operator 201, company cross-tenant 422, period invalido 422,
  Redis offline 502 sem tocar DB, enqueue estoura marca `failed`
  com audit, GET `queued` sem URL, GET cross-tenant 404, GET
  `ready` emite URL + audita sem vazar, viewer pode consultar) e
  3 integracao em `tests/test_build_export.py` (gated + moto +
  psycopg: happy path com 3 XMLs -> `ready` + file + 2
  notifications + `expires_at ≈ now+30d`; `EXPORT_MAX_BYTES=100`
  + 1 XML de 500B levanta `size_limit_exceeded` e zera
  notifications/files; periodo vazio -> `empty`). `pytest
  apps/api/tests/test_exports_schemas.py apps/api/tests/
  test_migration_0017.py` = 12 passed. Testes gated em `TEST_
  DATABASE_URL` seguem esqueleto de API-07/11. Nova dep run
  nenhuma (boto3 + tenacity + psycopg ja existem no workspace).
  DoD manual "export de 500 XMLs completa e download do ZIP abre"
  fica a cargo do owner apos o setup do B2 real + CI com Postgres
  (issue #8 + pipeline INFRA-09) — `moto` cobre o caminho feliz
  localmente. `excel_consolidated` e delivery real de notificacao
  ficam para tickets futuros conforme o escopo conservador deste
  entregavel (PR a abrir — Closes #39).

- **DS-08** — Estados e utilitarios de UX em `apps/web-app/components/ui/`:
  `empty-state.tsx` (card com icone Lucide opcional + CTA via `action`
  — suporta `onClick` ou `href` -> renderiza `<a>` para navegacao
  server-friendly; `role="status"` + `aria-live="polite"`),
  `loading-skeleton.tsx` (duas variantes: `lines` — N barras
  empilhadas com ultima em `w-2/3` para quebrar o ritmo — e `rows` —
  grade `rows x columns` com CSS grid inline; `rows` prevalece quando
  ambos setados; `aria-busy="true"` + `aria-label` customizavel),
  `error-boundary.tsx` (class component — limitacao da API do React
  para capturar erros de render; `getDerivedStateFromError` +
  `componentDidCatch` com `onError` opcional para telemetria; props
  `fallback` aceita node ou funcao `({error, reset}) => node`; UI
  default com `AlertTriangle` + mensagem + botao "Tentar novamente"
  que chama `onRetry`), `confirm-dialog.tsx` (reutiliza `Dialog` do
  DS-03 — sem Radix; props `confirmPhrase` + `tone: default |
  destructive`; quando `confirmPhrase` esta setado, input renderiza
  dentro de `DialogBody` e o botao "Confirmar" fica `disabled` ate
  `typed.trim() === confirmPhrase` — **prova do DoD**; `busy` trava
  tudo enquanto a acao esta em voo; reseta input quando dialog
  fecha), `timeline.tsx` (lista vertical `<ol>` com bullet colorido
  por tone — `default/success/warning/destructive/info` — e linha
  conectora absoluta; `<time dateTime={iso}>` para leitores; icone
  Lucide opcional dentro do bullet). 5 novas secoes em
  `app/styleguide/page.tsx` com demos dedicadas em
  `app/styleguide/<componente>-demo.tsx`. Testes novos (25 casos):
  `empty-state.test.tsx` (4 — titulo/desc, icone, onClick do CTA,
  variante `href` como link), `loading-skeleton.test.tsx` (4 —
  aria-busy, contagem de barras em `lines`, `rows x columns`,
  prioridade de `rows`), `error-boundary.test.tsx` (5 — filhos ok,
  fallback default, reset via `onRetry` com re-render, fallback custom
  funcao, `onError` recebe Error), `confirm-dialog.test.tsx` (7 —
  fechado nao monta, sem phrase habilita de cara, bloqueia ate match
  exato case-sensitive, aceita trim, tone destrutivo via `data-tone`,
  Cancelar dispara onClose, `busy` desabilita mesmo com match) e
  `timeline.test.tsx` (5 — ordem, aria-label, `dateTime` ISO no
  `<time>`, `data-tone` por item, lista vazia). `pnpm --filter
  web-app typecheck` limpo, `next lint` zero warnings, `vitest run`:
  264 passed (239 previos + 25 novos). Move DS-08 de "Bloqueadas"
  (dependencia DS-02 ja com artefatos — `tokens.css` + `/styleguide`
  + `theme-toggle` — em origin/main) para "Em Andamento"
  (PR a abrir — Closes #47).

- **DOCS-05** — Runbooks de infra (disco cheio, fila travada, SSL
  expirando, backup falhou): 4 arquivos novos em `docs/runbooks/`
  seguindo o mesmo template dos runbooks de dominio
  (`credencial-invalida.md`, `portal-indisponivel.md`): escopo,
  sintomas, **como detectar** (fontes de alerta — Uptime Kuma / Loki /
  Grafana — e checagem manual com comandos verificaveis), **diagnostico**
  (quem cresceu / por que travou / por que a renovacao nao aconteceu /
  exit code -> causa), **mitigacao** em ordem de menor blast radius
  primeiro, e **prevencao** com checklist durável. `disco-cheio.md` cobre
  `df`/`docker system prune`/rotacao de logs via `/etc/docker/daemon.json`/
  VACUUM/WAL travado em replication slot inativo/retencao Loki temporaria
  e ultimo recurso de upgrade de disco. `fila-travada.md` cobre RQ stuck
  com queries diretas em `rq:queue:nfse-executions`/`rq:started_registry`/
  `rq:failed:nfse-executions`, restart graceful (stop_grace_period 60s),
  scale-out temporario para drenar, limpeza de failed registry,
  re-enfileiramento via snippet Python, job fantasma via
  `StartedJobRegistry.cleanup()`, e encerramento manual de execution
  abandonada com occurrence `UNKNOWN`. `ssl-expirando.md` cobre
  `certbot renew --dry-run`, Cloudflare com proxy ligado (DNS-only
  necessario por INFRA-03), webroot ACME, reemissao cobrindo os 5
  hostnames SAN (apex/www/app/api/ops), e mitigacao de HSTS ativo com
  cert vencido. `backup-falhou.md` mapeia a matriz exit code -> causa
  do `infra/scripts/backup-postgres.sh` (2 config, 3 pg_dump, 4 age,
  5 upload S3, 6 cleanup), com testes idempotentes de cada camada,
  backup emergencial sem cifra como escape hatch de 24h, e caminho de
  drill de restore quando o upload vai bem mas o `.dump.age` nao abre.
  **DoD "Linkados no alerta correspondente em Grafana":** (a)
  `infra/compose/grafana/dashboards/api-worker-logs.json` ganha 4 links
  de dashboard (campo root `"links"`) apontando para os runbooks em
  `main` no GitHub — visiveis no topo do dashboard; (b) `infra/
  observability.md` ganha nova secao 9 "Runbooks de infra (DOCS-05)"
  com tabela cenario->runbook->alerta, instrucoes para preencher o campo
  Description de cada monitor Uptime Kuma com a URL do runbook (o
  Uptime Kuma ja inclui Description no payload do Telegram — operador
  chega direto no runbook), ativacao de "Certificate Expiry Notification"
  nos 4 monitores HTTPs, e template de `annotations.runbook_url` para
  alert rules Grafana futuras. Sem codigo executavel — so Markdown +
  JSON do dashboard; JSON validado por `python3 -c json.load`. Move
  DOCS-05 de "Proximas destravadas" para "Em Andamento"
  (PR a abrir — Closes #75).

## Concluidos (anteriores)

- **CORE-05** — Cliente S3 do worker-core em
  `packages/worker-core/worker_core/storage.py`: `S3StorageClient` com
  `upload_xml(tenant_id, execution_id, nsu, xml_bytes) -> UploadResult`
  e `upload_export(tenant_id, file_id, path_or_bytes, ext) ->
  UploadResult` (aceita `bytes` ou `str/PathLike`). `UploadResult`
  dataclass frozen carrega `object_key`, `sha256` (hex lowercase) e
  `size`. Key builders puros `xml_object_key` -> `tenants/{tid}/
  executions/{eid}/{nsu}.xml` e `export_object_key` ->
  `tenants-exports/{tid}/{fid}.{ext}` (alinhado ao ADR-003 + INFRA-06
  — B2 so aceita prefix literal em lifecycle, por isso exports ficam
  em prefix irmao). `S3Settings.from_env()` le as vars `S3_*` sem
  depender de `apps/api/config`. Cliente boto3 cacheado via
  `functools.lru_cache(maxsize=1)` com
  `signature_version=s3v4`/`addressing_style=path`/`retries` padrao
  `standard/3`. Content-Type `application/xml` para XML e mapa por
  extensao para exports (`xlsx`/`xls`/`csv`/`zip`/`pdf`/`json`) com
  fallback `application/octet-stream`; metadata inclui `sha256` + `nsu`
  ou `ext`. Retry com `tenacity`: `stop_after_attempt(4)` +
  `wait_exponential(0.5s..8s)` filtrado por `_is_transient` — retenta
  apenas `EndpointConnectionError` e `ClientError` em
  `{SlowDown, ServiceUnavailable, InternalError, RequestTimeout,
  ThrottlingException, 500, 503}`; erros definitivos (`AccessDenied`,
  `NoSuchBucket`, ...) propagam como `StorageError` sem retry. Logs
  em `logging.getLogger("worker_core.storage")` sem expor bytes.
  Validacoes: `nsu` `int >= 0` (bool explicitamente rejeitado), UUID
  aceita `UUID` ou `str`, `ext` normalizado (lowercase, sem ponto,
  alfanumerico), `body` precisa ser `bytes`/`bytearray`. Nova dep run
  `boto3>=1.34` e optional-dep `dev` com `moto[s3]>=5.0` +
  `pytest>=7.0`. Re-exports em `worker_core/__init__.py`. 30 testes em
  `tests/test_storage.py` (key builders, `S3Settings`, round-trip real
  via `moto.mock_aws`, retry sucesso/esgotamento/erros definitivos,
  `EndpointConnectionError` como transient). `pytest tests/
  --ignore=tests/test_main.py` = 130 passed. DoD "upload real para
  bucket de teste" permanece a cargo do owner apos o setup manual do
  B2 (issue #8) — sem isso o PUT contra Backblaze retorna 401; o
  smoke test local via `moto` ja cobre o caminho feliz. Integracao
  com `batch_processor` e adapter para o `StorageBackend` legado
  ficam para API-11 / CORE-04. Move CORE-05 de "Bloqueadas"
  (dependencias CORE-01 + INFRA-06 ja satisfeitas) para "Concluidos"
  (PR a abrir — Closes #23).
- **CORE-04** — Refactor: callback de progresso por item.
  Novo modulo `packages/worker-core/worker_core/collector.py` expondo
  `fetch_nfse(pfx_bytes, pfx_password, cnpj, nsu_source, on_progress,
  on_log=None, *, max_documentos=None, rate_limit_delay=0)`:
  abre `mtls_session` (CORE-02) internamente, pagina via
  `buscar_todos_dfe_novos` + `NsuSource` (CORE-03), filtra
  `TipoDocumento == "NFSE"` e emite `NfseItem` por nota em
  `on_progress`. `NfseItem` (`@dataclass(frozen=True)`) carrega os 9
  campos do ticket (`nsu`, `chave_nfse`, `cnpj_emitente`,
  `data_emissao`, `valor`, `xml_bytes`, `status`, `error_code`,
  `error_message`) com `status` em `{"ok","cancelada","parse_error"}`.
  Retorno `FetchSummary` (contadores + `nsu_from`/`nsu_to` +
  `callback_errors` + `fatal_rejected`). Garantias da DoD: (a) erro
  dentro de `on_progress` e capturado, registrado em
  `on_log("callback_error",...)` e a coleta continua; (b) XML ausente/
  invalido vira `NfseItem(status="parse_error")` emitido normalmente;
  (c) erros fatais (PFX/senha/cert vencido -> `ValueError` do
  `mtls_session`) propagam apos `on_log("fatal_error",
  {"stage":"mtls"})`. Re-exports em `worker_core/__init__.py`
  (`fetch_nfse`, `NfseItem`, `FetchSummary`) substituem o alias
  placeholder `fetch_nfse = buscar_todos_dfe_novos` do CORE-01;
  `buscar_todos_dfe_novos` segue disponivel em `worker_core.fetcher`
  para o coletor historico. 8 testes novos em
  `tests/test_fetch_nfse.py` com PFX self-signed em memoria e stubs
  de `mtls_session`/`buscar_lote_dfe` cobrindo a DoD completa.
  `pytest tests/` = 116 passed (108 anteriores + 8 novos). `ruff
  check` verde. README do pacote atualizado com secao
  "fetch_nfse (CORE-04)". Sem alteracoes em `batch_processor`/
  `main.py`/`src/` — comportamento legado preservado. Destrava
  API-13 (worker consumer) junto com CORE-05 + API-06 + API-07
  (PR a abrir — Closes #22).

- **CORE-03** — Refactor: NSU via callback (sem arquivo). Introduz em
  `packages/worker-core/worker_core/nsu_tracker.py` o protocolo
  `NsuSource` (`typing.Protocol` runtime-checkable, metodos
  `get(cnpj) -> int` e `set(cnpj, nsu)`) e duas implementacoes:
  `InMemoryNsuSource` (dict em memoria, `set` respeita "NSU nunca
  regride", expoe `snapshot()` para testes) e `FileNsuSource` (wrapper
  sobre `carregar_estado`/`salvar_estado`/`atualizar_nsu` preservando
  escrita atomica `.tmp` + `os.replace` e nao regressao; `set` so
  regrava o arquivo quando o dict muda de fato). As funcoes legadas
  (`carregar_estado`/`salvar_estado`/`obter_ultimo_nsu`/`atualizar_nsu`/
  `resetar_cnpj`) permanecem intactas para compat com `main.py --reset-nsu`
  e `src/diagnostico.py`. `worker_core.fetcher.buscar_todos_dfe_novos`
  ganha kwarg opcional `nsu_source: NsuSource | None = None`: quando
  fornecido, usa `source.get(cnpj)` como NSU inicial e chama
  `source.set(cnpj, maior_nsu)` no fim (so se o NSU progrediu);
  sem `nsu_source`, comportamento legado 100% preservado (o
  `batch_processor` e o CLI nao mudam de assinatura neste ticket). Tests
  novos: 16 casos em `tests/test_nsu_tracker.py` (InMemory/File — default
  zero, persistencia cross-instance, nao regressao em memoria e em disco,
  isolamento por CNPJ, `isinstance(..., NsuSource)`, nao-reescrita quando
  valor nao progride) e 5 casos em `tests/test_nfse_fetcher.py` cobrindo
  as 4 combinacoes (`get` define NSU inicial; `set` persistido com
  progresso; `set` nao chamado sem progresso; comportamento legado sem
  source) + integracao real com `InMemoryNsuSource`. `pytest tests/` em
  108 testes verdes. Re-exports em `worker_core/__init__.py`
  (`NsuSource`, `InMemoryNsuSource`, `FileNsuSource`) e nota no
  `packages/worker-core/README.md`. Adapter DB-backed fica para API-13
  conforme previsto no ticket
  (PR a abrir — Closes #21).

- **DATA-06** — Teste automatizado de isolamento cross-tenant: suite
  `apps/api/tests/test_rls_isolation.py` com 31 casos parametrizados
  que semeiam 2 tenants (A e B) em todas as 14 tabelas RLS (`tenants`,
  `tenant_users`, `companies`, `company_credentials`, `executions`,
  `execution_items`, `occurrences`, `reprocess_jobs`, `notifications`,
  `refresh_tokens`, `files`, `schedules`, `audit_logs`,
  `subscriptions`) e, via role `app_user` (`NOBYPASSRLS`), validam
  que: (a) `SELECT` com GUC de A devolve 0 linhas de B em cada tabela;
  (b) sem `SET LOCAL app.current_tenant` o `app_user` fica fail-closed
  (0 linhas em todas as 14); (c) `UPDATE`/`DELETE` cross-tenant tem
  `rowcount == 0`; (d) `INSERT` forjando `tenant_id` alheio dispara
  `InsufficientPrivilege` (`WITH CHECK` da policy). Fixtures em
  `apps/api/tests/conftest.py` (`rls_seed` scope=module com
  truncate+seed, `app_user_cursor` abrindo conexao nova com
  `SET LOCAL ROLE app_user` + `set_config('app.current_tenant', ...,
  true)`), gated em `TEST_DATABASE_URL` (mesmo padrao de API-02/03).
  Novo job `test-rls` em `.github/workflows/ci.yml` sobe service
  container `postgres:16`, aplica `alembic upgrade head` e roda o
  pytest em toda PR. Runbook de injecao de falha (`ALTER TABLE ...
  DISABLE ROW LEVEL SECURITY`) documentado em `apps/api/README.md`.
  Correcao incidental: migration `0015_merge_heads.py` (no-op) fecha
  o fork Alembic deixado por DATA-04/DATA-05 (`0008_notifications` e
  `0014_plans_subscriptions` eram heads independentes), desbloqueando
  `alembic upgrade head`. Move DATA-06 para "Em Andamento"
  (PR a abrir — Closes #17).
- **DATA-07** — Seed de dev idempotente em
  `apps/api/scripts/seed.py`: popula `plans` (`starter`/`pro`/`scale`
  com limites `jsonb` e precos em centavos), tenant `demo` (slug
  `demo`, plan `pro`, status `active`), user global `admin@demo.local`
  (senha vinda de `API_SEED_ADMIN_PASSWORD`, fallback `demo12345`
  apenas em `API_ENVIRONMENT=development`; aborta em staging/prod)
  e membership `owner`. Todas as escritas usam
  `ON CONFLICT ... DO UPDATE` (`plans.code`, `tenants.slug`,
  expressao `LOWER(email)` em `users`, PK composta em
  `tenant_users`), entao re-rodar nao duplica linhas. Usa
  `get_admin_session()` (BYPASSRLS) por rodar sem
  `app.current_tenant`. Invocavel via
  `cd apps/api && python -m scripts.seed` (pacote `scripts/` com
  `__init__.py`). 9 testes unitarios em
  `apps/api/tests/test_seed.py` (constantes, limites jsonb,
  fallback/abort da senha, `ON CONFLICT` nos 3 upserts) + 1 teste de
  integracao gated por `TEST_DATABASE_URL` rodando `run_seed()` duas
  vezes e validando idempotencia. Nova env
  `API_SEED_ADMIN_PASSWORD` em `config/.env.example`. Nao insere
  linha em `subscriptions` (billing adiado — ADR-004)
  (PR a abrir — Closes #18).
- **INFRA-09** — Pipeline de deploy (GitHub Actions -> SSH):
  workflows `.github/workflows/deploy-staging.yml` (push em `main` com
  paths `apps/api/**`, `packages/worker-core/**`, `infra/compose/**`,
  `infra/deploy/**`) e `.github/workflows/deploy-prod.yml` (push de tag
  `v*` + `workflow_dispatch` manual com input `tag`). Ambos fazem
  `docker/build-push-action@v6` do `apps/api/Dockerfile` para
  `ghcr.io/<owner>/nfse-api:<tag>` + `latest-{staging,prod}` via
  `GITHUB_TOKEN` (`permissions: packages: write`) com cache GHA, e em
  seguida `appleboy/ssh-action@v1.2.0` no VPS exportando
  `DEPLOY_ENV`+`DEPLOY_TAG` para `/srv/nfse/deploy.sh`. Script
  `infra/deploy/deploy.sh` (idempotente, `set -euo pipefail`):
  persiste tag anterior em `config/.last_deploy_tag` antes do
  `docker compose pull && up -d --remove-orphans`, aguarda health em
  `GET /health` (30 tentativas x 2s), e em falha reverte para a tag
  anterior + re-sobe e `exit 20` (marca workflow como falho apos
  rollback). Override `infra/compose/docker-compose.deploy.yml`
  adiciona o servico `api` consumindo `ghcr.io/...:${DEPLOY_TAG}` com
  `depends_on` healthy de Postgres/Redis (INFRA-05) e publica em
  `127.0.0.1:8000` para o Nginx host (INFRA-04); bloco do `worker`
  comentado aguardando CORE-05. Runbook completo em
  `infra/deploy/README.md` cobrindo preparacao do `/srv/nfse/<env>`
  (symlinks para compose files + `deploy.sh`), `docker login ghcr.io`
  com PAT `read:packages`, os 4 secrets do repo
  (`SSH_HOST`/`SSH_USER`/`SSH_KEY`/`GHCR_TOKEN` opcional),
  environment `prod` com approval manual, roteiro do DoD (rollback
  via `HEALTH_URL` falso + `workflow_dispatch`) e operacao
  (disparo manual, promocao staging->prod, rollback manual, logs).
  Concurrency `deploy-staging`/`deploy-prod` nao cancela em voo.
  Execucao real fica a cargo do owner — DoD (PR em main dispara
  staging; tag `v0.0.1` dispara prod; rollback manual ok) valida apos
  provisionamento dos secrets e do `/srv/nfse/` na VPS
  (PR a abrir — Closes #11).

- **INFRA-07** — Stack de observabilidade minima em
  `infra/compose/docker-compose.obs.yml`: `loki` (v2.9, retencao 14d,
  filesystem/boltdb-shipper), `promtail` (coleta
  `/var/lib/docker/containers` + `/var/log`, positions persistentes em
  `/srv/nfse/prod/data/promtail`), `grafana` (v10.4, bind
  `127.0.0.1:3001`, `GF_SERVER_SERVE_FROM_SUB_PATH=true`/root URL
  `/grafana`, datasource Loki + dashboard "NFS-e — Logs API & Worker"
  provisionados) e `uptime-kuma` (v1.23, bind `127.0.0.1:3002`). Configs
  versionados em `infra/compose/{loki,promtail,grafana}/...` e dashboard
  inicial em `infra/compose/grafana/dashboards/api-worker-logs.json`
  (paineis de logs `nfse-api`/`nfse-worker` + timeseries de taxa de erro
  em 5m). Server block Nginx em `infra/nginx/ops.conf.example` expoe
  `ops.<DOMINIO>/grafana` e `/uptime` com `satisfy all` (IP allowlist +
  basic auth via `/etc/nginx/.htpasswd-ops`), WebSocket para Grafana Live
  e Uptime Kuma, redirect 80->443 e headers de seguranca (HSTS,
  X-Frame-Options, Referrer-Policy). Runbook completo em
  `infra/observability.md` cobrindo estrutura de diretorios com UIDs
  corretos (Loki 10001, Grafana 472), subida da stack, htpasswd bcrypt,
  certbot, criacao dos 4 monitores (site/app/api/health/worker/healthz)
  e Notification Telegram com teste manual. Novas envs no bloco
  `# Observabilidade (INFRA-07)` do `config/.env.example`
  (`OBS_DOMAIN`, `GRAFANA_ADMIN_USER/PASSWORD`, `OPS_ALLOWED_IPS`,
  `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`). Execucao real fica a cargo
  do owner — DoD (Grafana acessivel, logs em tempo real, alerta Telegram
  dispara) valida apos aplicacao manual
  (PR a abrir — Closes #9).

- **INFRA-04** — Nginx no host + Let's Encrypt: runbook completo em
  `infra/nginx.md` (instalacao via apt no Ubuntu 24.04 noble, webroot
  ACME em `/var/www/letsencrypt/`, placeholder em `/var/www/em-breve/`,
  emissao SAN unico cobrindo apex + `www` + `app` + `api` + `ops` com
  `certbot --nginx --redirect`, `certbot renew --dry-run` e
  `certbot.timer` do systemd, HSTS desligado por padrao e ativado so
  apos validar HTTPS); configs versionadas em `infra/nginx/` com
  `nginx.conf` (overrides globais: worker_processes auto, gzip,
  log_format com `request_time`/upstream, `server_tokens off`),
  snippets `tls.conf` (TLS 1.2+, ciphers Mozilla intermediate, stapling,
  `ssl_dhparam`), `security-headers.conf` (HSTS comentado, X-Frame-Options
  DENY, X-Content-Type-Options, Referrer-Policy, Permissions-Policy,
  COOP/CORP), `rate-limit.conf` (`limit_req_zone auth_ip 10m 5r/s`),
  `proxy-common.conf` (X-Forwarded-*, Upgrade/Connection, timeouts) e
  `connection-upgrade.conf` (map WebSocket); server blocks
  `apex.conf` (301 -> www), `www.conf`/`app.conf`/`ops.conf` servindo
  `em-breve.html`, `api.conf` com `limit_req zone=auth_ip burst=10
  nodelay` em `location ^~ /auth/` (prova de rate limit do DoD) e
  `proxy_pass` comentado para `127.0.0.1:3000`/`127.0.0.1:8000`
  (descomenta em INFRA-05); reforco em `api`/`ops` de que DNS precisa
  ficar em DNS-only na Cloudflare (ADR-003 / INFRA-03). Execucao na
  VPS real fica a cargo do owner — DoD (SSL Labs A nos 5 hostnames,
  `certbot renew --dry-run` ok, configs commitadas) valida apos
  aplicacao manual (PR a abrir — Closes #6).

- **DS-06** — Componente `<DataTable>` server-side em
  `apps/web-app/components/ui/data-table/` baseado em TanStack Table +
  `@tanstack/react-query`: paginacao/ordenacao/filtragem manuais, estado
  preservado em `searchParams` (prefixo configuravel), filtros texto/
  select/date-range com draft local aplicado via botao/Enter, saved
  filters por tabela em `localStorage` (chave `dt:<queryKey>`), export
  CSV do resultado atual (RFC 4180 + BOM UTF-8), estados loading
  (skeleton rows), vazio e erro com "Tentar novamente". `AppQueryClient
  Provider` em `apps/web-app/components/providers/query-client-provider.tsx`
  wrappando o `RootLayout`. Demo com 10k linhas mockadas no `/styleguide`
  (`app/styleguide/data-table-demo.tsx` — dataset deterministico via
  Mulberry32, fetcher simulando latencia). Testes vitest: `csv.test.ts`
  (10 casos), `url-state.test.ts` (8 casos, roundtrip parse<->serialize)
  e `data-table.test.tsx` (5 casos — skeleton/vazio/linhas/erro+retry/
  paginacao chamando router.replace). Typecheck, lint e 56 testes verdes.
  Novas deps `@tanstack/react-table` e `@tanstack/react-query`
  (PR a abrir — Closes #45).
- **CORE-02** — Refactor `packages/worker-core/worker_core/auth.py` para
  aceitar PFX em memoria: novo context manager
  `mtls_session(pfx_bytes, pfx_password)` carrega o PFX direto dos bytes
  (vindo do banco cifrado — ADR-003), materializa cert PEM + key PEM em
  tmpfs (`/dev/shm`, fallback `tempfile.gettempdir()`) com `0o600` e
  garante remocao dos dois PEMs no `finally` (sucesso ou excecao);
  `certificate` exposto via `session.nfse_certificate`. Legado
  `criar_session_cliente(path, senha)` mantido como wrapper de compat
  (batch_processor e diagnostico nao mudam). Mensagens de erro sem path/
  senha/bytes quando o PFX vem de memoria. Testes em `tests/test_auth.py`
  (11 novos): fixture gera PFX self-signed em memoria via
  `cryptography.hazmat.primitives.serialization.pkcs12.serialize_key_and_certificates`;
  cobre sucesso, limpeza em excecao, senha errada, PFX vazio/nao-bytes,
  certificado vencido, ausencia de vazamento em logs (`caplog`),
  confirmacao de tmpfs e wrapper legacy. `pytest tests/` = 79 passed
  (PR a abrir — Closes #20).

- **APP-01** — Paginas de auth: `/login`, `/signup`, `/recuperar-senha`,
  `/redefinir-senha/[token]` e `/aceitar-convite/[token]` em
  `apps/web-app/app/(auth)/`; `<AuthProvider>` em
  `apps/web-app/components/auth/` com access token em memoria + refresh
  automatico; refresh token em cookie httpOnly gerenciado pelos Route
  Handlers `apps/web-app/app/api/auth/{signup,login,refresh,logout}/`
  (proxy fino para a API FastAPI — compensa API-02 devolver o refresh no
  body). `/dashboard` protegido por `<RequireAuth>`; user menu faz logout
  de verdade. Spec Playwright em `apps/web-app/e2e/auth.spec.ts`
  (signup->dashboard + refresh automatico) com `page.route` mockando
  `/api/auth/*` — roda local via `pnpm --filter web-app test:e2e`.
  Novas envs `NEXT_PUBLIC_API_BASE_URL` e `API_BASE_URL` em
  `config/.env.example`. Novas deps `zod`, `react-hook-form`,
  `@hookform/resolvers`, `@playwright/test`. Stubs de UI para
  recuperar/redefinir/aceitar-convite (backend correspondente ainda nao
  existe — endpoints a entregar em ticket API futuro).
  (PR a abrir — Closes #49).

- **DATA-02** — Schema de `companies` + `company_credentials`:
  migrations `0002_companies.py` (CNPJs por tenant, unique
  `(tenant_id, cnpj)`, RLS) e `0003_company_credentials.py` (PFX A1
  cifrado, FK composta `(tenant_id, company_id) -> companies`, indice
  em `cert_not_after` para alerta de vencimento, RLS) em
  `apps/api/alembic/versions/`. Testes estaticos em `apps/api/tests/`
  e runbook manual de isolamento cross-tenant em `apps/api/README.md`
  (PR a abrir — Closes #13).
- **DATA-05** — Schema das tabelas de suporte do MVP: migrations
  `0011_files.py` (sem `storage_tier` por ADR-003; tambem merge dos
  dois heads Alembic `0003_company_credentials` + `0010_auth_refresh_tokens`),
  `0012_schedules.py` (cron por tenant/company, FK composta, indice
  `(enabled, next_run_at)`), `0013_audit_logs.py` (bigserial, indice
  `(tenant_id, created_at DESC)`, metadata jsonb), e
  `0014_plans_subscriptions.py` (catalogo `plans` sem RLS +
  `subscriptions` com RLS; promove `tenants.plan_id` a FK ->
  `plans.code`). Testes estaticos em `apps/api/tests/test_migration_0011..0014.py`
  e teste de insercao massiva (10k rows) em
  `tests/test_audit_logs_bulk.py` (pulado sem `TEST_DATABASE_URL`)
  (PR a abrir — Closes #16).
- **DATA-03** — Schema de `executions` + `execution_items`:
  migrations `0004_executions.py` (uma corrida de coleta por
  tenant+company com FK composta para `companies`, indice
  `(tenant_id, company_id, started_at DESC)`, CHECKs de
  `trigger`/`status`/ordem do periodo/soma de itens, RLS) e
  `0005_execution_items.py` (um item por NFS-e processada com FK
  composta para `executions`, indices `(execution_id)` e
  `(tenant_id, data_emissao)`, indice unico parcial
  `(tenant_id, chave_nfse) WHERE chave_nfse IS NOT NULL`, RLS) em
  `apps/api/alembic/versions/`. Testes estaticos em
  `apps/api/tests/test_migration_0004.py` e `test_migration_0005.py`;
  runbook manual de isolamento cross-tenant + EXPLAIN verde da query
  de listagem por periodo em `apps/api/README.md`
  (PR a abrir — Closes #14).
- **API-03** — Middleware de tenant (GUC para RLS): dependencies
  `get_current_claims` / `assert_tenant_active` / `get_tenant_db` em
  `apps/api/api/deps.py`; endpoint `GET /auth/me` como prova de vida
  (RLS-gated count em `tenant_users`); 15 testes unitarios e 6 de
  integracao (gated por `TEST_DATABASE_URL`) em
  `apps/api/tests/test_tenant_middleware*.py`; runbook manual em
  `apps/api/README.md`. Tenant inexistente/`suspended`/`canceled` ->
  403; token ausente/invalido -> 401 com `WWW-Authenticate: Bearer`
  (PR a abrir — Closes #27).
- **API-04** — RBAC (owner/admin/operator/viewer): dependency
  `require_role(*allowed, min_role=None)` em
  `apps/api/api/security/rbac.py`, encadeando `assert_tenant_active`
  (API-03) e devolvendo 403 claro quando o papel nao e autorizado;
  guarda pura `ensure_can_manage_member` protegendo `owner` (apenas
  outro owner remove/rebaixa owner; admin nao promove acima do proprio
  papel) para uso pelos endpoints de membros a chegar; matriz completa
  em `docs/architecture/rbac-matrix.md` cobrindo tenant, membros,
  companies, executions e auditoria; 31 testes unitarios em
  `apps/api/tests/test_rbac.py` incluindo prova de DoD (viewer -> 403
  em `POST /_probe/companies` via router efemero e `require_role(min_role="owner")`
  somente permitindo owner). (PR a abrir — Closes #28).
- **INFRA-05** — Compose base com Postgres 16 e Redis 7 em
  `infra/compose/docker-compose.base.yml` (volumes nomeados `nfse_pgdata`
  e `nfse_redisdata`, network privada `nfse_internal`, portas publicadas
  apenas em `127.0.0.1`, healthchecks via `pg_isready` e `redis-cli ping`,
  Redis com `requirepass` + AOF, Postgres com locale `C.UTF-8`);
  `infra/compose/.env.example` documenta `POSTGRES_USER/PASSWORD/DB`,
  `REDIS_PASSWORD` e portas host; `.gitignore` local evita commit de
  `.env`; `infra/compose/README.md` traz setup, DoD, operacao
  (`up`/`down`/logs) e politica manual de backup (pg_dumpall + RDB em
  `/srv/nfse/<env>/backups/`, retencao 90d alinhada ao ADR-003 — automacao
  fica para INFRA-08). `infra/README.md` atualizado com a nova pasta
  `compose/` (PR a abrir — Closes #7).

- **DATA-04** — Schema de tabelas operacionais:
  migrations `0006_occurrences.py` (ocorrencias por tenant com FKs
  compostas para `companies` e `executions`, FK nullable para
  `users.assignee_user_id`, CHECKs de `severity`/`status`/ordem de
  `first_seen_at`/`last_seen_at`, RLS), `0007_reprocess_jobs.py`
  (jobs de reprocessamento com `scope jsonb`, `result_execution_ids
  text[]`, CHECK de `status`, RLS) e `0008_notifications.py`
  (outbox multicanal com `payload jsonb`, CHECKs de
  `channel`/`status`, indice parcial para pendentes, RLS) em
  `apps/api/alembic/versions/`. Testes estaticos em
  `apps/api/tests/test_migration_000{6,7,8}.py`
  (PR a abrir — Closes #15).
- **API-05** — CRUD de `/companies`: router em
  `apps/api/api/companies/` com `GET` paginado (filtros `status`/`uf`),
  `GET /{id}`, `POST` (valida DV de CNPJ e aplica limite de plano via
  `plans.limits.max_companies`), `PATCH` (CNPJ imutavel via
  `extra=forbid`) e `DELETE` soft (grava `deleted_at`). Nova migration
  `0015_companies_deleted_at.py` adiciona coluna `deleted_at
  TIMESTAMPTZ` e troca `uq_companies_tenant_cnpj` por UNIQUE parcial
  `WHERE deleted_at IS NULL` (permite reusar CNPJ apos soft-delete),
  alem de indice parcial de listagem. RBAC da matriz
  `docs/architecture/rbac-matrix.md`: leitura = todos; POST/PATCH =
  `owner|admin|operator`; DELETE = `owner|admin`. Validador de CNPJ
  (`companies/cnpj.py`) rejeita DV invalido e sequencias repetidas.
  38 testes unitarios (CNPJ, schemas, migration estatica) + 16 testes
  de integracao gated por `TEST_DATABASE_URL` cobrindo CRUD, cross-
  tenant via RLS, RBAC (viewer -> 403), soft-delete idempotente,
  reaproveitamento de CNPJ, filtros/paginacao e limite de plano
  (PR a abrir — Closes #29).

- **DATA-01** — Schema inicial de identidade: Alembic configurado em
  `apps/api/alembic/`, migration `0001_initial_identity.py` cria
  extensao `pgcrypto`, roles `app_admin` (BYPASSRLS) / `app_user`
  (NOBYPASSRLS), tabelas `tenants`, `users`, `tenant_users`, RLS +
  politicas em `tenants` e `tenant_users` via GUC `app.current_tenant`
  (PR #95). Desbloqueia DATA-02..DATA-07.
  (PR a abrir, issue #12).
- **API-02** — Auth: signup + login + JWT refresh rotativo. Endpoints
  `/auth/signup|login|refresh|logout` em `apps/api/api/auth/`, hash
  argon2id (`api/security/password.py`), JWT access 15min HS256
  (`api/security/jwt.py`), refresh opaco 7d com rotacao e detecao de
  reuso via `replaced_by` (`api/security/tokens.py`), rate limit
  slowapi 5/min/IP no login, migration `0010_auth_refresh_tokens.py`
  com RLS por tenant. Testes unitarios (argon2/JWT/hash) e E2E com
  `TEST_DATABASE_URL` opcional (PR a abrir, issue #26).
- **DS-03** — Layout shell: componente `<AppShell>` em
  `apps/web-app/components/app-shell/` com sidebar colapsavel
  (256px/64px em desktop, drawer em <1024px), topbar fixa com
  breadcrumbs (derivados de `usePathname`), tenant switcher placeholder,
  bell de notificacoes, theme toggle e user menu; dropdowns leves sem
  Radix (fecham em click-outside/Esc); rota `/dashboard` consumindo o
  shell com KPIs e tabela placeholder; landmarks ARIA + skip-link
  "Pular para o conteudo" + `focus-visible:ring`. Typecheck e
  `next lint` verdes (PR a abrir, issue #42).

- **DS-05** — Componente `KPIStatCard` em
  `apps/web-app/components/ui/kpi-stat-card.tsx` (props `title`, `value`,
  `deltaPercent?`, `trendData?`, `icon?`, `state?`, `hint?`,
  `errorMessage?`): card com valor grande, delta colorido (success/
  destructive/muted com seta Lucide), mini-sparkline via SVG inline
  (sem Recharts — evita dep extra e `use client` obrigatorio) e estados
  `ready`/`loading` (skeleton)/`empty` (valor `—`)/`error`
  (AlertTriangle + mensagem). Demo no `/styleguide` com 7 cards (4 em
  `ready` + loading/empty/error) via `app/styleguide/kpi-stat-card-demo.tsx`;
  `app/dashboard/page.tsx` refatorado para consumir o componente.
  Spec `components/ui/kpi-stat-card.test.tsx` com 7 snapshots cobrindo
  ready (sem delta/sparkline, delta positivo, delta negativo, delta
  zero), loading, empty e error, mais asserts de `aria-label`,
  `aria-busy` e de que `trendData` com <2 pontos nao renderiza a
  sparkline. Typecheck e `next lint` verdes (PR a abrir — Closes #44).

- **DS-04** — Componente `StatusBadge` (10 variantes) em
  `apps/web-app/components/ui/status-badge.tsx` com `variant`
  (`success`, `processing`, `pending`, `failed`, `warning`, `blocked`,
  `cert_expiring`, `cred_invalid`, `portal_unstable`, `reprocess_needed`)
  + `size` (`sm`, `md`), icone Lucide por variante e tooltip via
  atributo `title` nativo. Demo no styleguide em
  `apps/web-app/app/styleguide/status-badge-demo.tsx`. Bootstrap de
  vitest + jsdom + `@testing-library/react`/`jest-dom` (primeiro spec
  do `apps/web-app`, destrava o TODO de `test-ts` do GOV-06) com
  `vitest.config.ts` / `vitest.setup.ts` e suite de snapshot cobrindo
  as 10 variantes x 2 tamanhos (20 snapshots) + comportamento de
  override de label/tooltip e `hideIcon` (PR a abrir — Closes #43).

- **DS-02** — Design tokens + tema base: CSS vars para cores (paleta neutra +
  primaria azul + critica vermelha + success/warning) em light/dark,
  tipografia (Inter + JetBrains Mono via `next/font/google` com variaveis
  `--font-sans`/`--font-mono`), espacamento, radius e sombras em
  `apps/web-app/styles/tokens.css`; Tailwind estendido em
  `apps/web-app/tailwind.config.ts` mapeando os tokens; rota `/styleguide`
  (app router ignora diretorios com `_`, ajustado de `_styleguide` para
  `styleguide`) com amostras de todos os tokens; toggle light/dark
  (`components/theme-toggle.tsx`) com persistencia em `localStorage` e
  script inline anti-FOUC no `layout.tsx` (PR a abrir — Closes #41).

- **GOV-01/02/03** — Setup do monorepo (pnpm workspaces + Turborepo),
  5 ADRs iniciais e backlog completo em `docs/tasks/` com STATE.md e
  templates GitHub (PR #1).
- **GOV-07** — Workflow `.github/workflows/pr-guardrail.yml` exige
  STATE.md + CHANGELOG.md + `Closes #N` em todo PR para `main`
  (entregue junto com o setup inicial).
- **DS-01** — Bootstrap do `apps/web-app` (Next.js 14 App Router + TS
  strict, Tailwind, shadcn/ui, Lucide, Sonner) com pagina `/`
  "Hello painel" (PR #84).
- **API-01** — Bootstrap FastAPI em `apps/api/`: config via
  `pydantic-settings` (prefixo `API_`), logging JSON estruturado,
  endpoints `/health` e `/version`, Dockerfile multi-stage com usuario
  nao-root. Desbloqueia DATA-01.
- **CORE-01** — Motor ADN legado extraido de `src/` para pacote Python
  instalavel em `packages/worker-core/`; `src/` vira shim retro-compativel
  (PR #80).
- **INFRA-06** — Bucket S3 (Backblaze B2): parte automatizada entregue
  em PR #79 (template de lifecycle em `infra/s3-lifecycle.json`, variaveis
  `S3_*` em `config/.env.example`, smoke test em
  `infra/scripts/s3-smoke-test.sh`, runbook em `infra/s3-bucket.md`).
  Descoberta de design: B2 so aceita *prefix literal* em lifecycle rules,
  entao o bucket usa layout `tenants/` (XML 90d) + `tenants-exports/`
  (exports 30d), consumido via `S3_EXECUTIONS_PREFIX` e
  `S3_EXPORTS_PREFIX` (ADR-003 preservado). **Setup manual do owner em
  aberto** (7 itens — conta B2 + 2FA, bucket `nfse-saas-prod`
  private/versioning on/SSE-B2, 2 lifecycle rules aplicadas, Application
  Key least-privilege no prefix `tenants/`, cofre 1Password/Bitwarden,
  smoke test `[s3-smoke] PASS`, `aws s3 ls s3://$S3_BUCKET/tenants/` ok);
  rastreio permanece em #8 ate validacao.
- **INFRA-01** — Hardening inicial da VPS Hostinger: runbook completo
  em `infra/vps-hardening.md` (usuario `deploy`, SSH chave-only, UFW,
  fail2ban, unattended-upgrades, TZ `America/Sao_Paulo`). Execucao na
  VPS real fica a cargo do owner — DoD dos checks `ssh`/`ufw`/`fail2ban`/
  `timedatectl` e validado apos aplicacao manual.
- **INFRA-02** — Docker Engine + Compose v2 + diretorios padrao:
  runbook em `infra/vps-docker.md` (repo oficial `download.docker.com`,
  `docker-ce` + `buildx` + `compose-plugin`, `deploy` no grupo `docker`,
  log-driver `json-file` com rotacao 10m/3 e `live-restore`, arvore
  `/srv/nfse/{prod,staging}/{data,backups,logs,config}` com owner
  `deploy:deploy` e mode `0750`). Execucao na VPS real fica a cargo do
  owner — DoD (`docker compose version` >= 2.20, `docker ps` sem sudo,
  permissoes dos diretorios) validado apos aplicacao manual.
- **INFRA-03** — Runbook de DNS no Cloudflare em `infra/dns.md`: tabela
  de registros A para `app`/`api`/`ops`/`www`/apex com DNS-only
  obrigatorio em `api` e `ops` (preservar mTLS das prefeituras — ADR-003),
  passos via UI + API, checks `dig` e plano de migracao quando o nome
  comercial sair. Aplicacao na zona real (owner) — DoD valida apos
  propagacao.
- **DOCS-01** — Termos de Uso criado em `docs/legal/terms.md`, incluindo
  clausula de retencao de 90 dias (ADR-003), pagamento/renovacao/cancelamento,
  limitacao de responsabilidade, foro/legislacao e orientacao de referencia
  para signup e rota `/legal` do app/site (PR #81).
- **DOCS-02** — Politica de Privacidade (LGPD) publicada em
  `docs/legal/privacy.md` + RoPA minima em `docs/legal/ropa.md` (PR #87).
- **DOCS-03** — Runbook de credencial invalida criado em
  `docs/runbooks/credencial-invalida.md` e linkado no ticket APP-06 para
  uso inline nas ocorrencias `CERT_EXPIRED`, `CRED_INVALID` e
  `CERT_REVOKED` (PR #88).
- **DOCS-04** — Runbook de incidentes para indisponibilidade de portal
  e rate-limit documentado em `docs/runbooks/portal-indisponivel.md`
  (triagem, backoff, comunicacao e criterio de status page) (PR #89).
- **GOV-06** — CI base: workflow `.github/workflows/ci.yml` com jobs
  `lint-python` (ruff), `test-python` (pytest), `lint-ts` (eslint +
  typecheck) em todo PR e push em `main`; cache pip + pnpm;
  `ruff.toml` conservador na raiz. `test-ts` (vitest) fica como TODO
  ate o primeiro spec em `apps/web-app`. Branch protection com os
  checks `lint-python`, `test-python`, `lint-ts` obrigatorios em
  `main` precisa ser habilitada manualmente no GitHub (owner).

## Proximas Destravadas (prontas para iniciar)

_Backlog ativo aguardando priorizacao do owner._ A trilha CORE/API/DATA/
INFRA esta toda em `main` (ver "Concluidos"). Os proximos passos naturais
sao:

1. **Aplicar correcoes da auditoria** descritas em
   `docs/auditoria-tecnica-2026-04-22.md` — tres itens criticos abertos:
   (a) `_revoke_chain` em `apps/api/api/security/tokens.py` (CTE recursiva
   inverte o sentido `replaced_by`); (b) condicao de corrida em
   `apps/worker/worker/scheduler.py` (`_has_inflight_execution` +
   `_insert_execution` sem `pg_advisory_xact_lock`); (c) `.github/
   workflows/ci.yml` so roda `pytest tests/`, deixando
   `apps/api/tests/` e `apps/worker/tests/` fora do gate.
2. **Setup manual do bucket B2** (issue #8) — habilita os DoDs manuais
   pendentes em INFRA-06, API-06, API-11, API-15 e CORE-06 (upload real,
   download via URL pre-assinada, smoke E2E com PFX real).
3. **Provisionar VPS + secrets** (`SSH_HOST`/`SSH_USER`/`SSH_KEY` no
   GitHub e `/srv/nfse/<env>` no host) para habilitar o pipeline de
   deploy do INFRA-09. Apos isso, descomentar os `proxy_pass` em
   `infra/nginx/sites-available/{app,api}.conf` para o Nginx host
   comecar a rotear para os containers.
4. **Trilha SITE (00..10)** — bloqueada apenas pelo nome comercial /
   dominio definitivo (ver "Pendencias de Decisao").

## Bloqueadas

- **SITE-00..10** — aguardando definicao do nome comercial.

## Limite de WIP

Maximo **4 tarefas** em "Em Andamento" simultaneamente.

## Pendencias de Decisao

| Item | Prazo sugerido | Bloqueia |
|------|----------------|----------|
| Nome comercial / dominio definitivo | antes da Fase 7 | Trilha SITE inteira |
| Gateway de pagamento (Asaas/Stripe/Iugu) | antes do primeiro cliente pago | API de billing |

## Ultima atualizacao

- Data: 2026-04-29
- Revisao geral da documentacao na branch `claude/review-project-docs-2og85`:
  - Secao "Em Andamento" esvaziada — todas as 26 entregas que viviam ali
    (APP-02/03/04/05/06/07/08/09/10/11, API-06/07/08/09/10/11/12/13/14/15,
    CORE-06, DS-07/08/09, INFRA-08, DOCS-05) ja estao em `main` e foram
    movidas para "Concluidos (entregas recentes)".
  - "Concluidos" original renomeado para "Concluidos (anteriores)".
  - "Proximas Destravadas" reescrito em torno do que realmente destrava
    valor agora (correcoes da auditoria, setup manual do B2, secrets de
    deploy, nome comercial) — INFRA-05 saiu da lista (compose ja em main).
  - README, SETUP, TROUBLESHOOTING, CHANGELOG e `infra/deploy/README.md`
    revisados na mesma branch.

## Historico anterior (PRs ainda nao indexados aqui)

- PR: (a abrir) — APP-08: pagina `/arquivos` em
  `apps/web-app/app/arquivos/` consumindo API-11 (listagem + URL
  pre-assinada 1h) e API-15 (export ZIP assincrono). Lista paginada
  filtravel por `kind` (UI expoe XMLs/Exports/Relatorios; `pfx` e
  `other` ocultos como internos), `company` (select alimentado por
  `listCompanies(page_size=100)`) e `periodo` via `<PeriodPicker>`
  (DS-07) convertendo `YYYY-MM-DD` em ISO 8601 UTC com `to` exclusivo.
  **Banner de retencao permanente** (`retention-banner.tsx` com
  `role="note"` + `data-testid="retention-banner"`, nao descartavel,
  cobre retencao 90d default e 30d de exports) satisfaz DoD "banner
  visivel sempre" (ADR-003). Acao "Baixar" chama `getFileDownloadUrl`
  (API-11) e abre a URL pre-assinada 1h em nova aba via
  `window.open(url, "_blank", "noopener,noreferrer")` — a URL nunca e
  persistida no estado do front. `<GerarZipDialog>` (gated RBAC
  operator+) dispara `POST /exports kind="zip_xml"` e faz **polling em
  `GET /exports/{id}` a cada 3s** com maquina de estados declarativa
  (`idle | submitting | polling{status} | ready{record} | empty |
  failed | timed_out`) — `ready` exibe link `<a href={download_url}
  target="_blank">Baixar ZIP`, `empty` (status canonico de API-15)
  exibe mensagem amigavel, `timed_out` (10 min) orienta atualizar a
  pagina; modal fica nao-descartavel enquanto em `submitting|polling`.
  Ao atingir `ready` invalida a query `[files:list]` para que o novo
  `file` (kind=export) apareca na listagem sem refresh. Novos clientes
  HTTP em `apps/web-app/lib/api/`: `files.ts` (tipos `ApiFile`,
  `FileListResponse`, `FileUrlResponse`, `listFiles`,
  `getFileDownloadUrl`, `FilesApiError` com codigos `not_found`/
  `forbidden`/`unauthorized`/`presign_unavailable`/`validation_error`/
  `network`/`unknown`, helpers `FILE_KIND_LABEL`, `UI_FILTER_KINDS`,
  `formatBytes`) e `exports.ts` (tipos `ExportRecord`, `ExportStatus`,
  `createExport`, `getExport`, `isTerminalExportStatus`,
  `ExportsApiError` com codigos `company_not_found`/`queue_unavailable`/
  `validation_error`/`forbidden`/`unauthorized`/`not_found`/
  `presign_unavailable`/`network`/`unknown`). Ambos seguem o padrao de
  `lib/api/executions.ts` (reusam `apiFetch` com retry unico em 401 via
  `tryRefresh`, aceitam `ApiCallContext`, mapeiam `ApiError` em
  codigos canonicos). Item **"Arquivos"** (icone `FolderArchive`) em
  `components/app-shell/nav-items.ts` entre "Ocorrencias" e "Notas".
  Testes novos: 17 em `lib/api/files.test.ts` (buildListQuery + GET
  feliz + mapeamentos 403/422/404/502/rede + helpers
  `formatBytes`/`UI_FILTER_KINDS`/`FILE_KIND_LABEL`), 11 em
  `lib/api/exports.test.ts` (POST feliz + `enqueue_failed` preserva
  `status=failed` + 422 `company_not_found` + 502 `queue_unavailable`
  + `getExport` ready/not_found + `isTerminalExportStatus`), 6 em
  `app/arquivos/arquivos-view.test.tsx` (banner sempre presente mesmo
  com lista vazia, empty state, linha renderizada, `window.open` com
  `noopener,noreferrer`, troca de filtro `kind=export` dispara nova
  query, viewer nao ve botao "Gerar ZIP") e 4 em
  `app/arquivos/gerar-zip-dialog.test.tsx` (submit sem empresa nao
  chama `createExport`, polling `running -> ready` exibe link de
  download com `href` batendo `download_url`, `status=empty` exibe
  painel dedicado, `ExportsApiError(queue_unavailable)` mostra a
  mensagem). Polling testado com `vi.useFakeTimers({shouldAdvanceTime:
  true})` + `vi.advanceTimersByTimeAsync(3000)`; usa `fireEvent`
  (projeto nao tem `@testing-library/user-event`). `pnpm typecheck`,
  `pnpm lint` (`next lint`) e `pnpm test` (`vitest run`) verdes —
  **433 testes em 48 arquivos** (400 anteriores + 33 novos). Decisao
  consciente de **nao resolver nome da empresa** quando o filtro nao
  esta aplicado (API-11 so expoe `source_execution_id`) — exibe
  "Execucao {uuid-curto}…" como fallback; enriquecimento server-side
  fica como follow-up. Decisao consciente de **omitir kinds `pfx`/
  `other`** do filtro da UI. DoD "download funciona" coberto
  estruturalmente pelos mocks; validacao empirica com bucket B2 real
  fica com o owner (issue #8). Move APP-08 de "Bloqueadas" (dependencias
  API-11 #128 e API-15 #140 ja em `main`) para "Em Andamento".
  Closes #56.
- PR: (a abrir) — APP-11: wizard de onboarding em 3 passos (cadastrar
  empresa -> subir PFX -> rodar 1a coleta). Novo pacote
  `apps/web-app/components/onboarding/` montado em `<RequireAuth>`
  (cobre todas as rotas autenticadas). Deteccao do passo atual e 100%
  derivada do backend (`use-onboarding-state`: listCompanies +
  fetchCredential + listExecutions(status=succeeded|partial)), sem
  migration. Skip visivel mas destacado como nao recomendado suprime
  modal por 24h via localStorage `nfse:onboarding:dismissed:<tid>:<uid>`.
  Passo 3 dispara `POST /onboarding/first-collection-done` (novo endpoint
  FastAPI em `apps/api/api/onboarding/routes.py`, registrado em
  `main.py`) — grava linha idempotente em `notifications`
  (channel=email, type=first_collection_done, payload={}) por
  (tenant_id, user_id, type); entrega SMTP fica como tech debt ate o
  consumer de outbox existir. Novos schemas em `onboarding/schemas.py`
  (`FirstCollectionDoneOut` com `already_recorded + notification_id`).
  RBAC: qualquer membro autenticado registra (owner|admin|operator|
  viewer). Novo cliente `lib/api/onboarding.ts`. Drive-by fix em
  `apps/web-app/lib/api/{executions,occurrences}.ts` e
  `apps/web-app/components/app-shell/nav-items.ts` — o merge do PR #152
  deixou artefatos de conflito (interfaces duplicadas, imports soltos,
  array nao fechado) que explodiam `pnpm typecheck` com ~50 erros de
  sintaxe. Reconstrucao minima preserva ambos os shapes de input
  (camelCase de APP-05 + snake_case de APP-02) sem refatorar nenhum
  consumidor. `pnpm typecheck`/`pnpm lint` verdes; `pnpm test` = 44
  files / 398 passed (+8 do wizard). 5 testes de integracao novos em
  `apps/api/tests/test_onboarding_routes_integration.py` gated por
  `TEST_DATABASE_URL`. Move APP-11 de "Bloqueadas" para "Em Andamento".
  Closes #59.
- PR: (a abrir) — DOCS-05: runbooks de infra (disco cheio, fila
  travada, SSL expirando, backup falhou). 4 novos arquivos em
  `docs/runbooks/` seguindo o template dos runbooks de dominio
  (`credencial-invalida.md`, `portal-indisponivel.md`) com secoes
  escopo / sintomas / como detectar / diagnostico / mitigacao /
  prevencao; cada runbook cruza referencia com `infra/*.md` e com os
  demais runbooks. `disco-cheio.md` cobre Docker prune, rotacao de
  logs via `daemon.json`, VACUUM/WAL travado, Loki retencao
  temporaria e ultimo recurso (upgrade de disco). `fila-travada.md`
  cobre healthz do worker, inspecao de `rq:queue:*`/`rq:started_registry`/
  `rq:failed:*` via redis-cli, restart graceful (stop_grace_period
  60s do API-13), scale-out temporario e limpeza de failed registry.
  `ssl-expirando.md` cobre `certbot renew --dry-run`, Cloudflare
  DNS-only (INFRA-03), reemissao cobrindo os 5 hostnames SAN e HSTS
  desligado por padrao. `backup-falhou.md` mapeia os exit codes do
  `infra/scripts/backup-postgres.sh` (INFRA-08), com backup
  emergencial sem cifra como escape hatch de 24h e drill de restore
  para sanidade do dump. **DoD "Linkados no alerta correspondente em
  Grafana":** (a) `infra/compose/grafana/dashboards/api-worker-logs.json`
  ganha 4 links de dashboard (campo `"links"` root) apontando para
  `main` no GitHub — visiveis no topo do dashboard; (b)
  `infra/observability.md` ganha secao 9 "Runbooks de infra (DOCS-05)"
  com tabela cenario->runbook->alerta, instrucao de preencher o
  Description de cada monitor Uptime Kuma com a URL do runbook
  (Telegram inclui Description no payload -> operador vai direto ao
  runbook) e template de `annotations.runbook_url` para alert rules
  Grafana futuras. Sem codigo executavel; JSON do dashboard validado
  com `python3 -c json.load`. Move DOCS-05 para "Em Andamento".
  Closes #75.
- PR: (a abrir) — APP-07: pagina `/agendamentos` consumindo API-12
  (ja mergeada em main via #130). Nova rota
  `apps/web-app/app/agendamentos/` com layout (RequireAuth + AppShell),
  `page.tsx` + `agendamentos-view.tsx` (react-query,
  `listSchedules`/`listSchedulePresets`/`listCompanies`, tabela com
  cron humanizado, timezone, proximo run, toggle on/off que faz
  PATCH `{ enabled }` — reflete em `next_run_at` pelo backend cumprindo
  DoD, confirm() nativo no delete, RBAC alinhado a matriz) +
  `schedule-form-dialog.tsx` (builder 4 modos radio
  daily|weekly|monthly|custom, presets chips do backend, select de
  empresa + TZ + hora/minuto, preview "Proximos 5 runs" client-side,
  cron invalida bloqueia submit com mensagem clara cumprindo segunda
  DoD, erros 400/403/404 do backend viram alert contextual). Novo
  modulo puro `lib/schedules/cron.ts` (parser 5-campos com `*`/range/
  step/list, `humanizeCron` com fallback custom, `computeNextRuns`
  iterando minutos com `Intl.DateTimeFormat` para DST + lookahead
  2 anos, `builderToCron`/`cronToBuilder` round-trip) + cliente HTTP
  `lib/api/schedules.ts` (CRUD, toggle, extractErrorDetail). Novo
  item "Agendamentos" (icone `CalendarClock`) em
  `components/app-shell/nav-items.ts` entre "Empresas" e "Notas". 47
  testes vitest novos (35 cron + 12 client + 7 view + 7 dialog).
  `pnpm test` = 300 passed em 30 files; `tsc --noEmit` verde;
  `next lint` zero warnings. Move APP-07 de "Bloqueadas" para
  "Em Andamento". Closes #55.
- PR: (a abrir) — APP-06: inbox `/ocorrencias` consumindo API-09, com
  lista filtravel (status/severity/company_id), detalhe renderizando
  runbook inline por codigo (via `react-markdown` + route handler que
  le `docs/runbooks/<slug>.md` do disco), acoes acknowledge/resolve
  (nota obrigatoria)/assign/reprocessar (link para APP-05 futuro) — 3
  mutacoes invalidam cache react-query para atualizar estado sem
  reload. 4 runbooks novos criados para cobrir `REPROCESS_NEEDED`,
  `PARSE_ERROR`, `STORAGE_ERROR` e `UNKNOWN` — catalogo em
  `docs/architecture/occurrence-codes.md` fica com 11 codigos x 6
  runbooks (DoD "10 codigos" cumprido). Aba `occurrences-tab.tsx` do
  detalhe de empresa (APP-03) vira CTA para o inbox pre-filtrado por
  `company_id`. Novo item "Ocorrencias" no sidebar
  (`components/app-shell/nav-items.ts`). Novas deps
  `react-markdown`/`remark-gfm`. 22 testes vitest novos; `pnpm
  typecheck`/`next lint`/`vitest run` = 261 passed + zero warnings.
  Move APP-06 de "Bloqueadas" para "Em Andamento" — API-09 (PR #127)
  ja mergeada. Closes #54.
- PR: (a abrir) — APP-05: `/execucoes/nova` + acompanhamento
  real-time. Novo cliente `apps/web-app/lib/api/executions.ts`
  (tipos, `listExecutions`/`getExecution`/`listExecutionItems`/
  `createExecutions`, `ExecutionsApiError` mapeando 401/403/404/422/
  502 em codigos canonicos incluindo `credential_missing_or_expired`
  e `queue_unavailable` com `extra.companyIds`, helpers
  `decideExecutionBadge`/`computeProgress`/`isTerminalStatus`). Tres
  paginas em `apps/web-app/app/execucoes/`: (a) `/execucoes` —
  lista paginada com filtro por status, CTA "Nova execucao";
  (b) `/execucoes/nova` — `NovaExecucaoForm` client com multi-select
  de companies ativas + `<PeriodPicker>` (DS-07, default `last_30d`)
  + toggle dry-run + toggle "incremental desde ultimo NSU"
  (informativo — o worker ja respeita `last_nsu` internamente).
  Viewer ve alerta sem permissao; operator+ submete e e
  redirecionado pra `/execucoes/{id}` (N=1) ou `/execucoes` (N>1).
  Em 422 `credential_missing_or_expired`, traduz a mensagem
  listando CNPJs afetados com orientacao pra regularizar credencial
  (APP-04); (c) `/execucoes/[id]` — `ExecucaoDetailView` com
  `<StatusBadge>`, barra `role="progressbar"` (aria-valuenow/max),
  KPIs total/ok/fail, tabela de items com tabs-filter
  Todos/OK/Falhou/Ignorados/Pendentes + checkbox por linha e botao
  "Reprocessar selecionados (N)" desabilitado via `aria-disabled` +
  `title` citando APP-06/API-10. **Polling 2s** via `refetchInterval`
  do react-query (`isTerminalStatus(data.status)` desliga o polling
  quando status terminal — succeeded/failed/cancelled/partial),
  aplicado a detail e items. Sidebar ganha "Execucoes" (PlayCircle).
  Stub `executions-tab.tsx` (aba empresa) deixa de ser informativo
  e mostra as 5 execucoes mais recentes da company + link "Nova
  execucao?company_id=X". Testes: `lib/api/executions.test.ts` (16),
  `app/execucoes/nova/nova-execucao-form.test.tsx` (7, gating por
  papel + redirecionamentos N=1/N>1 + dry_run + traducao 422/502),
  `app/execucoes/[id]/execucao-detail-view.test.tsx` (7, progressbar
  aria, polling 2s real timers, 404, filtro por status, reprocess
  desabilitado). E2E `e2e/execucoes.spec.ts` cobrindo DoD literal
  (cria -> acompanha -> ve itens aparecendo via page.route). `pnpm
  typecheck`, `pnpm lint` e `pnpm test` verdes (29 arquivos / 269
  specs). Closes #53.
- Data: 2026-04-16
- PR: (a abrir) — APP-02: dashboard com KPIs em `/dashboard`.
  `apps/web-app/app/dashboard/page.tsx` passa a renderizar
  `<DashboardView/>` (novo em `components/dashboard/dashboard-view.tsx`)
  com: `PeriodPicker` (DS-07) controlado localmente em `useState`
  inicializado em `current_month`; 4 `<KPIStatCard>` (DS-05) em
  `kpi-cards.tsx` consumindo react-query em paralelo — (1) "Notas
  coletadas no periodo" soma `items_ok` da 1a pagina do
  `GET /executions?from&to&page_size=100` e marca aproximado (`1.234+`)
  quando `total > 100`; (2) "Execucoes OK / total" = 2 chamadas
  `page_size=1` usando `total` do envelope (sem e com
  `status=succeeded`); (3) "Ocorrencias abertas" = `GET /occurrences?`
  `status=open&page_size=1`, reflete estado atual sem filtro de
  periodo (decisao explicita); (4) "Certificados a vencer em 30d"
  fica em `state="empty"` com hint de follow-up — API-06 popula
  `cert_not_after` mas nao expoe listagem REST agregada; timeline
  provisoria em `recent-timeline.tsx` lista as 10 execucoes mais
  recentes do periodo com dot por status e link
  `/execucoes/{id}` (substitutivel sem mudar API publica quando
  DS-08 entregar `<Timeline>` canonico); atalhos "Nova execucao" ->
  `/execucoes/nova` (APP-05) e "Ver ocorrencias" -> `/ocorrencias`
  (APP-06). Clientes API novos `lib/api/executions.ts`
  (`listExecutions` + `periodDateToUtcIso` mapeando `YYYY-MM-DD` ->
  ISO 8601 UTC com `to` exclusivo — `endExclusive` avanca 1 dia
  porque a API filtra `started_at < to`) e `lib/api/occurrences.ts`
  (`listOccurrences`), ambos via `apiFetch` + `ApiError`. Specs
  vitest `components/dashboard/dashboard-view.test.tsx` (5 casos:
  renderiza 4 cards + atalhos com `href` corretos, timeline com
  10 items linkando `/execucoes/{id}`, empty state da timeline,
  KPI ocorrencias exibe `total`, card de certificados defensivamente
  `data-state="empty"`). `pnpm typecheck` + `pnpm lint` + `pnpm test`
  (27 arquivos / 244 testes) verdes. Follow-ups rastreados: endpoint
  `GET /credentials?expiring_in_days=30` e agregacao server-side em
  `GET /executions` (hoje paginacao client-side cobre o dashboard com
  limite aproximado). Move APP-02 para "Em Andamento" (deps DS-05 +
  API-08 mergeadas em `main`). Closes #50.
- PR: (a abrir) — DS-09: cliente API TypeScript gerado do OpenAPI.
  Nova camada `apps/web-app/lib/api/` com `generated/schema.d.ts`
  (emitido por `openapi-typescript` v7), `client.ts` (factory
  `createApiClient` + singleton sobre `openapi-fetch` v0.13 com
  middleware que injeta `Authorization: Bearer <token>` e retenta
  uma unica vez em 401 via `tryRefresh` da APP-01 — `onAuthFailure`
  faz redirect hard para `/login` em caso de falha; header sentinela
  `x-ds09-retry: 1` evita loop), `types.ts` (re-exports de
  `paths`/`components`/`operations`), `hooks.ts` (hooks react-query
  base `useHealth`/`useVersion`/`useMe`/`useCompanies`/`useExecutions`)
  e `README.md`. Script
  `apps/web-app/scripts/generate-api.mjs` (expoe `pnpm --filter
  web-app generate-api`, aceita `--url`/`--file` ou `API_OPENAPI_URL`,
  default `http://localhost:8000/openapi.json`) chama
  `openapiTS` + `astToString` e so reescreve quando o conteudo muda —
  idempotencia do DoD validada rodando duas vezes consecutivas.
  Novas deps em `apps/web-app/package.json`: `openapi-fetch@^0.13`
  (run) e `openapi-typescript@^7` (dev). 8 testes vitest novos
  (`lib/api/client.test.ts` com 5, `lib/api/hooks.test.tsx` com 3)
  cobrindo injecao de Authorization, retry pos-refresh, redirect em
  falha de refresh e prova de nao-loop. Clientes legados em
  `lib/api/companies.ts`, `lib/auth/api-client.ts`,
  `lib/users/api-client.ts` e `lib/companies/credentials.ts`
  preservados sem alteracao — migracao para o novo cliente ficara
  para tickets APP especificos. `pnpm --filter web-app typecheck` /
  `lint` / `vitest run` verdes (247 passed). Move DS-09 de
  "Bloqueadas" (dependencias DS-01 e API-01 concluidas) para "Em
  Andamento". Closes #48.
- PR: (a abrir) — API-14: scheduler de execucoes agendadas em
  `apps/worker/worker/scheduler.py` + `cron_utils.py`. Processo
  separado (`python -m worker.scheduler` / `nfse-scheduler`) com
  `apscheduler.BlockingScheduler` disparando `run_tick()` a cada
  minuto (`CronTrigger(minute="*", timezone="UTC")` +
  `coalesce=True`/`max_instances=1`/`misfire_grace_time=30`). Tick
  seleciona `schedules WHERE enabled=true AND next_run_at <= now()`
  via `get_admin_session`, resolve companies alvo (uma ou tenant-wide
  quando `company_id IS NULL`), checa overlap (`executions` em
  `queued`/`running` para a mesma company -> occurrence
  `SCHEDULE_OVERLAP` sem duplicar), cria `executions` com
  `trigger='schedule'` e enfileira `worker_core.jobs.run_execution`
  na mesma fila RQ usada por API-07, recomputa `next_run_at` e marca
  `last_run_at=now()` so quando ao menos 1 execucao foi criada. Novas
  deps `apscheduler>=3.10` + `croniter>=2.0` em
  `apps/worker/pyproject.toml` + script `nfse-scheduler`. Adiciona
  occurrence `SCHEDULE_OVERLAP` (severity `warning`) em
  `docs/architecture/occurrence-codes.md`. README do worker ganha
  secao "Scheduler (API-14)" com instrucao de override de `CMD` no
  compose reusando a mesma imagem do worker. Inclui drive-by fix em
  `packages/worker-core/worker_core/jobs.py` que tinha SyntaxError
  por merge conflict mal resolvido no PR #140 (duas module-level
  docstrings consecutivas). 34 testes novos em `apps/worker/tests/`
  passando + suite do worker-core destravada (32 passed). Move API-14
  de "Bloqueadas" (deps API-12 + API-13 mergeadas em main) para "Em
  Andamento". Closes #38.
- PR: (a abrir) — API-10: `POST /reprocess` + `GET /reprocess/{id}`
  em `apps/api/api/reprocess/` (3 escopos: `execution_item_ids[]`,
  `company_id + nsus[]`, `company_id + period[ + statuses]` — exatamente
  1 via `model_validator`). POST resolve o escopo em tuplas
  `(company_id, period_start, period_end)` distintas, valida companies +
  credenciais (reusa helpers de `executions/routes`), pre-pinga Redis,
  cria `reprocess_jobs` (status `queued`, scope jsonb canonizado com
  `kind`) + N `executions` com `trigger='reprocess'`, atualiza
  `result_execution_ids` e enfileira jobs RQ (`worker_core.jobs.run_execution`,
  mesmo pipeline de API-07). Enqueue falha -> execution filha marcada
  `failed`; todas falharem -> `reprocess_job` vira `failed` com
  `error_summary='enqueue_failed_all'`. Audit `reprocess.create` sem
  vazar company/period. GET agrega contadores via JOIN com `executions`
  por `result_execution_ids` e devolve `effective_status` (`running`/
  `succeeded`/`partial`/`failed`/`cancelled`). Granularidade honesta:
  o worker sempre refaz a janela completa — idempotencia do unique
  parcial em `execution_items` (0005) garante DoD "reprocessa 1 de 3
  items falhos, v2 atualiza status". Router registrado em `main.py`.
  Matriz RBAC ganha secao Reprocess; placeholder invalido
  `POST /executions/{id}/reprocess` da secao Executions substituido
  por nota. Sem migration nova — `reprocess_jobs` vem de DATA-04
  (0007). 20 unit tests + 19 integration gated (TEST_DATABASE_URL +
  fakeredis). Move API-10 de "Bloqueadas" para "Em Andamento". Closes #34.
- PR: (a abrir) — DS-08: estados e utilitarios de UX em
  `apps/web-app/components/ui/` — `EmptyState`, `LoadingSkeleton`
  (variantes `lines` e `rows`), `ErrorBoundary` (class component com
  `fallback` node/funcao e botao "Tentar novamente" via `onRetry`),
  `ConfirmDialog` (reutiliza `Dialog` do DS-03; `confirmPhrase` +
  `tone: destructive` — botao Confirmar bloqueado ate `typed.trim()
  === confirmPhrase` -> **prova do DoD**) e `Timeline` (lista
  vertical com bullet colorido por tone e `<time dateTime>`). 5
  secoes novas em `app/styleguide/page.tsx` com demos por componente.
  25 testes vitest novos. `pnpm --filter web-app typecheck` limpo,
  `next lint` zero warnings, `vitest run`: 264 passed. Move DS-08 de
  "Bloqueadas" (DS-02 em origin/main) para "Em Andamento". Closes #47.
- PR: (a abrir) — API-13: worker consumer RQ orquestrando execucao
  ponta-a-ponta. Novo pacote `apps/worker/` (entry point `python -m
  worker.main` lendo `API_REDIS_URL`+`API_QUEUE_NAME`; `HealthzServer`
  stdlib com `GET /healthz` em porta `WORKER_HEALTHZ_PORT` default
  8080; Dockerfile multi-stage non-root `worker:1002` com HEALTHCHECK
  + `STOPSIGNAL SIGTERM`; SIGTERM/SIGINT handlers delegam pra
  `Worker.request_stop` — graceful shutdown DoD cumprido com
  `stop_grace_period: 60s` no compose). Novos adapters em
  `packages/worker-core/worker_core/`: `crypto.py` (decrypt AES-GCM
  compat API-06 — mesmo `_VERSION_TAG`/HKDF/KEK env, duplicacao
  intencional com nota de fonte canonica), `db.py`
  (`get_admin_session`/`get_tenant_session` SQLAlchemy + `SET LOCAL
  app.current_tenant` para RLS), `db_nsu.py` (`DbNsuSource`
  persistindo `companies.last_nsu` via UPDATE only-if-greater),
  `jobs.py` (`run_execution(execution_id)` — fluxo 5 passos:
  carrega contexto, decifra PFX, chama `fetch_nfse` com callback
  que INSERT-a `execution_items` com `ON CONFLICT DO NOTHING`
  (idempotencia DoD) + upload XML S3, marca status via
  `_decide_final_status`, cria `occurrences` categorizadas
  `CRED_INVALID`/`CERT_EXPIRED`/`PORTAL_5XX`/`PARSE_ERROR`/
  `STORAGE_ERROR`/`UNKNOWN`). Novas deps run em worker-core
  (`sqlalchemy>=2`, `psycopg[binary]>=3.1`, `redis>=5`, `rq>=1.16`)
  + dev (`fakeredis>=2.20`). Novo bloco `# Worker RQ (apps/worker -
  API-13)` em `config/.env.example`. Re-exports de `run_execution`
  e `DbNsuSource` em `worker_core/__init__.py`. Testes: 10
  `tests/test_crypto_worker.py` (round-trip, tampering, KEK
  checks), 9 `tests/test_db_nsu.py` (UPDATE only-if-greater,
  mismatch de CNPJ), 13 `tests/test_jobs.py` (sucesso/partial/
  failed/idempotencia/fatal_rejected/storage_error/not_found +
  `_decide_final_status` parametrico), 3
  `apps/worker/tests/test_healthz.py` e 9
  `apps/worker/tests/test_main.py`. `pytest tests/
  --ignore=test_main.py --ignore=test_storage.py` = 140 passed;
  `pytest apps/worker/tests/` = 12 passed. DoD E2E real
  (postgres+redis+B2) validado manualmente pos-deploy; unit +
  integracao-ready aqui. Move API-13 de "Bloqueadas" (deps
  API-07/CORE-04/CORE-05/API-06 mergeadas em main) para "Em
  Andamento". Closes #37.
- PR: (a abrir) — API-08: listar/detalhar executions + execution_items.
  Novos endpoints `GET /executions` (paginado, filtros
  `company_id`/`status`/`from`/`to` sobre `started_at`),
  `GET /executions/{id}/items` (paginado, filtros `status`/`nsu`,
  ORDER `nsu ASC NULLS LAST`) e atalho
  `GET /companies/{id}/executions` em
  `apps/api/api/executions/routes.py` + `apps/api/api/companies/routes.py`
  (atalho valida 404 da company antes de delegar ao helper compartilhado
  `query_executions`). RBAC leitura liberada para todos os papeis
  (matriz). Schemas novos `ExecutionListOut`/`ExecutionItemOut`/
  `ExecutionItemListOut`/`ExecutionItemStatus` em
  `apps/api/api/executions/schemas.py`. Migration
  `0017_executions_listing_index.py` cria 2 indices auxiliares em
  `executions` (`ix_executions_tenant_started`,
  `ix_executions_tenant_status_started`) para satisfazer o DoD "EXPLAIN
  usa indice"; composto existente
  `ix_executions_tenant_company_started` (0004) entra quando
  `company_id` esta presente; `ix_execution_items_execution_id` (0005)
  ja serve a listagem de items. Detalhe `GET /executions/{id}` (entregue
  por API-07) ja cobre "contadores agregados" via `items_total/ok/fail`.
  5 testes unitarios em `test_executions_schemas.py` + 14 de integracao
  gated por `TEST_DATABASE_URL` em
  `test_executions_routes_integration.py` + 3 estaticos em
  `test_migration_0017.py`. Secao "Listagem de executions/
  execution_items — API-08" em `apps/api/README.md` com 3 EXPLAINs
  esperados e receita de paginacao em 10k items. Move API-08 para
  "Em Andamento" (dependencias API-07 + DATA-03 ambas concluidas).
  Closes #32.
- PR: (a abrir) — CORE-06: smoke test E2E
  `mtls_session` -> `fetch_nfse` -> `S3StorageClient` em
  `packages/worker-core/scripts/smoke.py` (executavel via
  `python -m scripts.smoke`). Recebe PFX por `--pfx`, CNPJ por
  `--cnpj`, senha **apenas** via env `NFSE_PFX_PASSWORD` (jamais
  flag); flags `--dias` (filtro client-side por `data_emissao`),
  `--max-documentos`, `--rate-limit`, `--ambiente`, `--nsu-inicial`,
  `--tenant-id`/`--execution-id` (UUID explicito ou aleatorio),
  `--dry-run` (curto-circuita o S3 e e default em ambiente sem
  `S3_*`) e `--verbose`. Exit codes discretos: 0 ok, 1 uso/config,
  2 fatal mTLS, 3 rede/upload. `_emit_log` imprime eventos JSON em
  uma linha **filtrando explicitamente** `pfx_password`/`pfx_bytes`
  alem do que o `worker_core.collector` ja sanitiza; resumo final
  legivel cobre `nsu_from`/`nsu_to` + contadores do `FetchSummary` +
  `uploads_ok`/`uploads_failed`/`filtered_by_date`/`bytes_total` +
  amostra dos 3 primeiros `object_key`. README do worker-core ganha
  secao "Smoke test E2E (CORE-06)" com bloco de envs (dry-run + real),
  recomendacao de `--max-documentos 50` na primeira rodada e alerta
  "NUNCA commite `.pfx`, senha ou chaves S3". Testes novos em
  `tests/test_smoke.py` (13 casos cobrindo `_within_window`,
  `_parse_args`/`_validate_args`, ausencia de `NFSE_PFX_PASSWORD`,
  filtro de `pfx_password` em `_emit_log` e callback do
  `_make_progress_callback` em 3 cenarios). `pytest tests/
  --ignore=tests/test_main.py` = 151 passed (138 anteriores + 13
  novos). Sem dependencias novas. DoD itens "smoke rodado com 1 CNPJ
  real" e "XML aparece no bucket com object key correto" permanecem
  a cargo do owner apos setup manual do bucket B2 (issue #8) e
  disponibilidade de PFX A1 real — caminho feliz local validado pelos
  testes de CORE-04 (fetcher mock) + CORE-05 (`moto.mock_aws`) e
  exercitavel via `--dry-run`. Move CORE-06 para "Em Andamento" (todas
  as dependencias CORE-02..05 ja em "Concluidos"). Closes #24.
- PR: (a abrir) — INFRA-08: backup diario do Postgres para S3.
  Scripts `infra/scripts/backup-postgres.sh` (pg_dump -Fc via
  `docker compose exec`, daily/monthly por prefix, cifra opcional com
  age, upload via `aws s3 cp`, retencao local configuravel, log JSON
  estruturado) e `infra/scripts/restore-postgres.sh` (--latest /
  --key + --target-db para drill, decifra age se necessario,
  `pg_restore --clean --if-exists --no-owner`, checksum de sanidade).
  Systemd template `infra/systemd/nfse-backup-postgres@.{service,timer}`
  com `OnCalendar=*-*-* 03:00:00` no TZ do host (`America/Sao_Paulo`
  via INFRA-01), `Persistent=true`, `RandomizedDelaySec=5min`,
  `EnvironmentFile=/srv/nfse/%i/config/.env`, hardening basico.
  Duas rules novas em `infra/s3-lifecycle.json` (`backups/postgres/daily/`
  30d, `backups/postgres/monthly/` 365d — separacao por prefix porque
  B2 nao suporta lifecycle por tag). Novo bloco
  `# Backup Postgres (INFRA-08)` em `config/.env.example` com 7
  variaveis. Runbook completo em `infra/backup.md` (pre-requisitos,
  geracao de par age, symlinks, install + enable do timer, uso manual,
  drill de restore em staging, troubleshooting, checklist DoD). Atualiza
  `infra/s3-bucket.md` para mencionar os 2 novos prefixos de backup no
  layout de chaves e o total de 4 rules no bucket. Move INFRA-08 de
  "Bloqueadas" para "Em Andamento" (dependencias INFRA-05 e parte
  automatizada de INFRA-06 ja concluidas). Closes #10.
- PR: (a abrir) — APP-04: aba "Credencial" em
  `/dashboard/empresas/[id]/credencial` com `<StatusBadge>` +
  fingerprint + validade, dialog de upload (`<FileDropzone>` + 
  `<SecretField>`, erros 400/413/502/403 traduzidos), ConfirmDialog
  de revogacao "digite REVOGAR" e placeholder desabilitado de
  "Testar agora" (aguarda endpoint futuro de handshake). Inclui no
  escopo o `GET /companies/{id}/credential` (RBAC leitura = todos;
  devolve credencial `active` mais recente ou 404; `cn_matches_cnpj`
  vira `None` porque o CN nao e persistido em
  `company_credentials`). Novo `components/ui/dialog.tsx` (modal
  acessivel sem Radix, focus trap + Esc + overlay click). Cliente
  tipado + mapeador de erros + `formatFingerprint` +
  `decideCredentialBadge` em
  `apps/web-app/lib/companies/credentials.ts`. 37 testes novos no
  web-app (helpers/status/upload/revoke/panel) + 4 testes de
  integracao no api cobrindo GET feliz sem ciphertext, GET 404 sem
  upload, GET 404 apos revoke e GET viewer autorizado. `pytest
  apps/api` = 163 passed + 72 skipped; `pnpm --filter web-app
  test` = 164 passed; `pnpm typecheck` / `pnpm lint` / `ruff
  check apps/api` limpos. Move APP-04 de "Bloqueadas" para "Em
  Andamento". Closes #52.
- PR: (a abrir) — APP-03: paginas `/empresas` (lista com `<DataTable>`
  filtrando `status` + `uf`, botao "Nova empresa" gated por papel) e
  `/empresas/[id]` com 6 abas lazy (`React.lazy` + `Suspense` em
  `company-tabs.tsx`; `data-tab-panel` so se preenche apos visita).
  Aba "Visao geral" entrega CRUD completo (Editar para
  `owner|admin|operator`, Excluir para `owner|admin`, com confirm
  modal e invalidacao dos caches react-query); abas Execucoes/
  Credencial/Agendamentos/Arquivos/Ocorrencias entram como stubs
  informativos apontando os tickets que vao entrega-las (APP-04..08,
  API-07/09/10). Novo cliente HTTP `lib/api/companies.ts`
  reaproveitando `apiFetch` da APP-01. Novo `components/ui/modal.tsx`
  (sem Radix — focus trap, Esc, click no backdrop, scroll lock no body)
  consumido pelo `NovaEmpresaDialog` (form react-hook-form + zod
  validando CNPJ via `isValidCnpj`/DS-07, UF e codigo IBGE) e pelos
  dialogs Editar/Excluir do overview. Item "Empresas" adicionado em
  `components/app-shell/nav-items.ts` (substitui placeholder
  "Tenants"). Filtro "ultimo sucesso" do ticket fica como **coluna
  apenas** porque API-05 nao expoe `?last_success_after=`; nota inline
  no codigo + na descricao do PR sugerindo extender o endpoint num
  ticket futuro. 20 novos testes vitest (`lib/api/companies.test.ts`,
  `app/empresas/empresas-view.test.tsx`,
  `app/empresas/[id]/company-tabs.test.tsx`) cobrindo querystring +
  header Authorization, gating por papel, e prova de lazy mount nas
  abas. Typecheck verde, `next lint` zero warnings, `vitest run` 142
  passed (+20 vs main). Move APP-03 de "Bloqueadas" para "Em Andamento".
  Closes #51.
- Data: 2026-04-15
- PR: (a abrir) — CORE-05: cliente S3 em
  `packages/worker-core/worker_core/storage.py` com `S3StorageClient`,
  `upload_xml`, `upload_export`, key builders puros (`xml_object_key`,
  `export_object_key`), `UploadResult(object_key, sha256, size)`,
  `S3Settings.from_env()` lendo `S3_*` sem depender de `apps/api`, boto3
  com `signature_version=s3v4` + retry `standard/3` no botocore + retry
  explicito via `tenacity` (`stop_after_attempt(4)` +
  `wait_exponential(0.5..8s)`, filtrado em `_is_transient` apenas para
  `SlowDown`/`ServiceUnavailable`/`InternalError`/`RequestTimeout`/
  `Throttling*`/`500`/`503` e `EndpointConnectionError` —
  `AccessDenied`/`NoSuchBucket` propagam sem retry). Content-Type mapa
  por ext para exports + fallback octet-stream; metadata `sha256` + `nsu`
  ou `ext`; logs em `worker_core.storage` sem expor bytes. Nova dep run
  `boto3>=1.34`, optional-dep `dev` com `moto[s3]>=5.0` + `pytest>=7.0`.
  Re-exports em `worker_core/__init__.py`. 30 testes em
  `tests/test_storage.py` (key builders, `S3Settings`, round-trip via
  `moto.mock_aws`, retry sucesso/esgotamento/erros definitivos). `pytest
  tests/ --ignore=tests/test_main.py` = 130 passed. Integracao com
  `batch_processor` e schema `files` ficam para API-11 / CORE-04 —
  este ticket entrega apenas o cliente reusavel. DoD "upload real em
  bucket de teste" depende do setup manual do B2 (issue #8) — sem isso
  o PUT em Backblaze retorna 401; o smoke test local via `moto` cobre o
  caminho feliz. Move CORE-05 de "Bloqueadas" para "Concluidos".
  Closes #23.
- PR: (a abrir) — API-09: inbox de ocorrencias operacionais em
  `apps/api/api/occurrences/` com `GET /occurrences` (paginado +
  filtros `status`/`severity`/`company_id`), `GET /occurrences/{id}`,
  `POST /occurrences/{id}/acknowledge` (idempotente em `ack`, 409 em
  estado terminal), `POST /occurrences/{id}/resolve` (`note`
  obrigatoria via `OccurrenceResolveIn` com `extra='forbid'`; nota
  registrada em `audit_logs.metadata.note`; grava `resolved_at`) e
  `POST /occurrences/{id}/assign` (valida membership do tenant
  via `tenant_users`; 404 para user inexistente ou de outro tenant).
  RBAC: leitura para todos os papeis, escrita para
  `owner|admin|operator` (viewer -> 403). Cada acao mutadora grava
  `audit_logs` com `action='occurrence.<verb>'` e metadata sem
  segredos. Catalogo canonico de codigos em
  `docs/architecture/occurrence-codes.md` (CERT_EXPIRED/EXPIRING/
  REVOKED, CRED_INVALID, PORTAL_5XX/TIMEOUT, RATE_LIMIT,
  REPROCESS_NEEDED, PARSE_ERROR, STORAGE_ERROR, UNKNOWN). Matriz RBAC
  atualizada em `docs/architecture/rbac-matrix.md`. 11 testes
  unitarios de schema + 22 testes de integracao gated por
  `TEST_DATABASE_URL` cobrindo DoD (transicoes de status + audit log
  por acao). Move API-09 de "Bloqueadas" para "Em Andamento" — DATA-04
  ja concluida. Closes #33.
- PR: (a abrir) — API-12: CRUD de `/schedules` em
  `apps/api/api/schedules/` (pacote novo com `cron.py` + `presets.py` +
  `schemas.py` + `routes.py`). Endpoints `GET /schedules` (paginado,
  filtros `enabled`/`company_id`), `GET /schedules/{id}`,
  `GET /schedules/presets`, `POST`, `PATCH`, `DELETE`. Cron 5-campos
  via `croniter` (rejeita 6/7 campos explicitamente), TZ via
  `zoneinfo.ZoneInfo`, `next_run_at` calculado na TZ local e persistido
  em UTC. `PATCH` recomputa `next_run_at` quando `cron_expr`/`timezone`
  mudam ou quando `enabled` vira true; limpa quando vira false.
  RBAC: leitura = todos; POST/PATCH = owner|admin|operator; DELETE =
  owner|admin (matriz atualizada em `docs/architecture/rbac-matrix.md`).
  Nova dep `croniter>=2.0` em `apps/api/pyproject.toml`. 41 unit tests
  (cron + schemas) + 18 integracao (gated `TEST_DATABASE_URL`) cobrindo
  DoD ("cron invalido -> 400 claro" e "`next_run_at` coerente com cron
  + TZ"). `pytest apps/api` = 204 passed + 86 skipped, 0 falhas. Move
  API-12 de "Bloqueadas" (dependencia DATA-05 ja em "Concluidos") para
  "Em Andamento". Closes #36.
- PR: (a abrir) — API-11: `/files` com listagem paginada e URL
  pre-assinada (1h). Novo pacote `apps/api/api/files/`
  (`schemas.py` + `routes.py`) expondo `GET /files` com filtros
  `kind`/`company`/`from`/`to` + paginacao e
  `GET /files/{id}/url` gerando presigned GET de 3600s e auditando
  `file.download_url` sem gravar a URL em si. Filtro por `company`
  usa JOIN em `executions` via `files.source_execution_id`. Novo
  helper `generate_presigned_get_url` em `apps/api/api/storage.py`
  (TTL clampado em 0 < s <= 7d). RBAC: leitura liberada para todos
  os papeis (viewer incluido) alinhado com a matriz. Cross-tenant
  -> 404 via RLS de `files`. Router registrado em
  `apps/api/api/main.py`. 4 unit tests + 12 integracao gated por
  `TEST_DATABASE_URL` + moto. `pytest apps/api`: 153 passed + 79
  skipped. Sem migration nova. Move API-11 de "Proximas
  Destravadas" para "Em Andamento". DoD manual (URL no navegador)
  fica para owner apos setup real do B2. Closes #35.
- PR: (a abrir) — API-07: `POST /executions` + `GET /executions/{id}`
  em `apps/api/api/executions/`. Router cria 1 linha em `executions`
  por `company_id` validado (RLS + credencial ativa com
  `cert_not_after > now()`), pre-pinga Redis (502 sem tocar DB em
  indisponibilidade) e enfileira `worker_core.jobs.run_execution`
  (via string, worker resolve import no pick) em fila RQ configurada
  por `API_REDIS_URL` + `API_QUEUE_NAME`. Novo
  `apps/api/api/queue.py` com `QueueError` agnostico, singletons
  lazy do Redis/Queue e helpers de teste. `dry_run` vai apenas no
  `meta` do job (nao persiste no schema). Falha no enqueue pos-INSERT
  marca a linha como `failed` com `error_summary='enqueue_failed'`.
  RBAC: POST = `owner|admin|operator`, GET = todos. Novas deps run
  `redis>=5.0`, `rq>=1.16`; dev `fakeredis>=2.20`. Novo bloco
  `# Fila Redis para execucoes (API-07)` em `config/.env.example`.
  12 unit de schemas + 7 unit da queue (fakeredis+RQ) + 10 de
  integracao gated por `TEST_DATABASE_URL` (fakeredis). `ruff check
  apps/api/` verde, `pytest apps/api` = 178 passed + 72 skipped.
  Move API-07 de "Bloqueadas" (desbloqueado por API-05 + INFRA-05
  ambos concluidos) para "Em Andamento". Closes #31.
- PR: (a abrir) — APP-10: pagina `/assinatura` placeholder sem
  gateway. Nova rota `apps/web-app/app/dashboard/assinatura/page.tsx`
  (server component) mostra plano atribuido + status (`<StatusBadge>`),
  tres `<UsageMeter>` (CNPJs, Execucoes no mes, Usuarios) com
  `used/limit` + `role="progressbar"` + tom ok/warn/full, mensagem
  "Para alterar plano, entre em contato com o suporte" com links
  WhatsApp + email (placeholders ate SITE-*) e placeholder vazio de
  historico de faturas. **Sem** botao de upgrade (ADR-004). Dados
  de teste em `apps/web-app/lib/subscription/mock.ts` com shape
  alinhado a `plans.limits` (DATA-07) para plug-in do endpoint
  futuro. Componente novo reutilizavel
  `apps/web-app/components/subscription/usage-meter.tsx` extrai o
  card de uso que antes estava inline na page (preserva `data-tone`,
  `aria-valuenow={used}`, `aria-valuemax={limit}`, clamp em 100% e
  tratamento de `limit=0`). Novo item `Assinatura` (icone
  `CreditCard`) em `components/app-shell/nav-items.ts`. Specs:
  `app/dashboard/assinatura/page.test.tsx` (6 casos: plano+badge,
  3 cards com progressbar, tone=full em 5/5, links wa.me/mailto,
  ausencia defensiva de CTAs de upgrade, placeholder vazio de
  faturas) + `components/subscription/usage-meter.test.tsx` (7
  casos: titulo/used/limit/%, aria-valuenow/min/max, thresholds
  ok/warn/full, clamp em 100%, limit=0 sem div/0). `tsc --noEmit`,
  `next lint` e `vitest run` verdes (13 arquivos, 135 testes).
  APP-10 estava `ready` apos DS-03 (ja concluido) — move para
  "Em Andamento". Closes #58.
- PR: (a abrir) — CORE-04: callback de progresso por item.
  Novo modulo `packages/worker-core/worker_core/collector.py` com
  `fetch_nfse(pfx_bytes, pfx_password, cnpj, nsu_source, on_progress,
  on_log=None, *, max_documentos=None, rate_limit_delay=0)` que abre
  `mtls_session` (CORE-02) internamente, pagina via
  `buscar_todos_dfe_novos` + `NsuSource` (CORE-03) e emite `NfseItem`
  por nota em `on_progress`. `NfseItem` (`@dataclass(frozen=True)`)
  carrega os 9 campos do ticket; `status` em
  `{"ok","cancelada","parse_error"}`. Retorno `FetchSummary` com
  contadores + `nsu_from`/`nsu_to` + `callback_errors` +
  `fatal_rejected`. Erro dentro do callback e XML corrompido nao
  abortam o lote (DoD CORE-04); erros fatais do `mtls_session` (PFX,
  senha, cert vencido) propagam apos `on_log("fatal_error",...)`.
  Substitui o alias placeholder `fetch_nfse = buscar_todos_dfe_novos`
  do CORE-01; `buscar_todos_dfe_novos` segue exportado em
  `worker_core.fetcher` para o coletor historico. 8 testes novos em
  `tests/test_fetch_nfse.py`. `pytest tests/` = 116 passed. `ruff
  check` verde. README do pacote atualizado. Move CORE-04 de
  "Bloqueadas" (dependia de CORE-02 + CORE-03, ambos concluidos) para
  "Concluidos". Closes #22.
- Data: 2026-04-16
- PR: (a abrir) — APP-09: `/usuarios` + convites. Pagina
  `apps/web-app/app/usuarios/` (RequireAuth + AppShell) com lista
  de membros, menu de acoes por linha (alterar papel, remover) e
  secao de convites pendentes (revogar). Camada
  `apps/web-app/lib/users/` (`types`/`schemas`/`api-client`/`rbac`)
  e componentes em `apps/web-app/components/users/` (`Modal`,
  `ConfirmDialog`, `RoleSelect`, `RoleBadge`, `InviteDialog`,
  `MembersTable`, `PendingInvitations`). RBAC do cliente espelha
  `docs/architecture/rbac-matrix.md` (admin nao atribui
  owner/admin; owner e protegido). Rota `/aceitar-convite/[token]`
  deixa de ser stub e chama `POST /api/auth/accept-invitation`
  (novo Route Handler proxy que grava o cookie httpOnly do refresh
  e devolve a sessao). Sidebar ganha entrada "Usuarios". 42 novos
  specs vitest (164 total passando) + E2E Playwright
  `e2e/usuarios.spec.ts` cobrindo convite feliz, aceite +
  redirecionamento pro dashboard e admin bloqueado sobre owner.
  Backend (`/tenant/members`, `/tenant/invitations*`) sera entregue
  em ticket API futuro — mesmo padrao APP-01. Move APP-09 de
  "Bloqueadas" para "Em Andamento". Closes #57.
- PR: (a abrir) — CORE-03: refactor do `nsu_tracker` para callbacks.
  Novo protocolo `NsuSource` (`get`/`set`) em
  `packages/worker-core/worker_core/nsu_tracker.py` com duas
  implementacoes padrao — `InMemoryNsuSource` (estado em dict, usada em
  testes e como buffer do worker DB-backed) e `FileNsuSource` (compat
  com `config/estado/ultimo_nsu.json`, preserva escrita atomica e a
  regra "NSU nunca regride"). `worker_core.fetcher.buscar_todos_dfe_novos`
  aceita `nsu_source: NsuSource | None = None`: quando fornecido, o
  fetcher le/escreve o NSU pelo source; sem ele, comportamento legado
  (batch_processor intocado). Funcoes legadas mantidas para
  `main.py --reset-nsu` e `src/diagnostico.py`. 16 novos testes em
  `tests/test_nsu_tracker.py` (InMemory/File) + 5 em
  `tests/test_nfse_fetcher.py` (integracao `fetcher` x `NsuSource`).
  `pytest tests/` = 108 passed. Re-exports em
  `packages/worker-core/worker_core/__init__.py` e nota no
  `packages/worker-core/README.md`. Adapter DB-backed fica para
  API-13. Move CORE-03 de "Bloqueadas" (dependia de CORE-01, ja
  mergeado em PR #80) para "Concluidos". Closes #21.
- PR: (a abrir) — INFRA-06 (follow-up administrativo): atualiza entrada
  em "Concluidos" com a descoberta do layout `tenants/` (90d) +
  `tenants-exports/` (30d) imposta pelo prefix-literal do B2 e explicita
  que os 7 passos manuais do owner seguem em aberto (rastreio em #8).
  Remove a menção a INFRA-06 da nota de bloqueio em "Proximas
  Destravadas" — CORE-05 / API-06 / API-11 / INFRA-08 passam a poder
  consumir a parte automatizada (template de lifecycle, variaveis
  `S3_*`, smoke test) sem esperar o setup manual. Sem mudanca em
  `infra/s3-bucket.md` alem de reforco do aviso de DoD manual pendente
  no topo da seção 5. Refs #8 (nao fecha — os 7 manuais continuam
  abertos). Titulo/commit `docs:` para bypass do `pr-guardrail`.
- PR: (a abrir) — DATA-06: teste automatizado de isolamento
  cross-tenant. Nova suite `apps/api/tests/test_rls_isolation.py`
  (31 testes parametrizados) + fixtures em
  `apps/api/tests/conftest.py` (dois tenants semeados em todas as 14
  tabelas RLS + context manager que troca a role para `app_user` e
  seta a GUC `app.current_tenant`). Novo job `test-rls` em
  `.github/workflows/ci.yml` com service container `postgres:16` e
  `alembic upgrade head`. Runbook de injecao de falha no
  `apps/api/README.md`. Migration incidental
  `0015_merge_heads.py` (no-op) fecha o fork Alembic deixado por
  DATA-04/DATA-05 — `alembic heads` volta a reportar 1 ponta.
  Move DATA-06 para "Em Andamento". Closes #17.
- PR: (a abrir) — DATA-07: seed de dev idempotente em
  `apps/api/scripts/seed.py` (plans `starter`/`pro`/`scale` +
  tenant `demo` + user `admin@demo.local` + membership `owner`).
  Todas as escritas usam `ON CONFLICT ... DO UPDATE`. Senha vem de
  `API_SEED_ADMIN_PASSWORD` com fallback dev (`demo12345`) e abort
  em staging/prod. Pacote `apps/api/scripts/` com `__init__.py`
  destravando `python -m scripts.seed`. 9 testes unitarios + 1 de
  integracao (idempotencia) gated por `TEST_DATABASE_URL` em
  `apps/api/tests/test_seed.py`. Nova env
  `API_SEED_ADMIN_PASSWORD` em `config/.env.example`. Nova secao
  "Seeds de dev" em `apps/api/README.md`. Move DATA-07 de
  "Bloqueadas" para "Em Andamento". Closes #18.
- PR: (a abrir) — INFRA-09: pipeline de deploy (GitHub Actions -> SSH).
  Workflows `.github/workflows/deploy-staging.yml` (push em `main`) e
  `deploy-prod.yml` (push de tag `v*` + `workflow_dispatch`) fazem
  `docker/build-push-action@v6` do `apps/api/Dockerfile` para GHCR
  (`ghcr.io/<owner>/nfse-api:<tag>` + `latest-{staging,prod}`) via
  `GITHUB_TOKEN` com cache GHA, e `appleboy/ssh-action@v1.2.0` no VPS
  rodando `infra/deploy/deploy.sh` — que grava a tag anterior em
  `/srv/nfse/<env>/config/.last_deploy_tag`, faz
  `docker compose pull && up -d --remove-orphans`, aguarda
  `GET /health` (30x2s) e reverte para a tag anterior em caso de falha
  (`exit 20` marca o workflow como falho pos-rollback). Override
  `infra/compose/docker-compose.deploy.yml` adiciona o servico `api`
  ancorado em `${DEPLOY_TAG}` (bloco do `worker` comentado ate
  CORE-05). Runbook `infra/deploy/README.md` documenta provisionamento
  do `/srv/nfse/<env>` (symlinks para compose + `deploy.sh`),
  `docker login ghcr.io` com PAT `read:packages`, os 4 secrets do repo
  e roteiro do DoD incluindo rollback manual via `workflow_dispatch`.
  Move INFRA-09 de "bloqueadas" (dependias INFRA-02+GOV-06, ja
  concluidas) para "Em Andamento". Closes #11.
- PR: (a abrir) — API-05: CRUD de `/companies` em
  `apps/api/api/companies/` (router + `cnpj.py` validando DV + schemas
  Pydantic com normalizacao de CNPJ/UF e `extra=forbid` em PATCH);
  dependencies FastAPI `require_role` aplicadas pela matriz RBAC;
  limite `plans.limits.max_companies` aplicado no POST; soft-delete via
  `deleted_at`. Nova migration `0015_companies_deleted_at.py`
  (coluna + UNIQUE parcial + indice de listagem). Router registrado em
  `api/main.py` (OpenAPI `/docs`). 38 unit tests (CNPJ + schemas +
  migration estatica) + 16 integracao gated por `TEST_DATABASE_URL`.
  Move API-05 de "Bloqueadas" para "Em Andamento". Closes #29.
- PR: (a abrir) — INFRA-07: stack de observabilidade
  (Loki 2.9 + Promtail + Grafana 10.4 + Uptime Kuma 1.23) em
  `infra/compose/docker-compose.obs.yml`, com configs versionados
  (`loki-config.yml`, `promtail-config.yml`, provisioning de datasource
  Loki e dashboard "NFS-e — Logs API & Worker" em JSON), server block
  Nginx em `infra/nginx/ops.conf.example` protegendo `ops.<DOMINIO>`
  por IP allowlist + basic auth bcrypt (`satisfy all`), e runbook
  completo em `infra/observability.md` (diretorios com UIDs corretos,
  htpasswd, certbot, 4 monitores no Uptime Kuma, Notification Telegram
  testada). Novo bloco `# Observabilidade (INFRA-07)` em
  `config/.env.example` com placeholders para `OBS_DOMAIN`,
  `GRAFANA_ADMIN_USER/PASSWORD`, `OPS_ALLOWED_IPS`, `TELEGRAM_BOT_TOKEN`
  e `TELEGRAM_CHAT_ID`. Move INFRA-07 para "Em Andamento". Closes #9.
- PR: (a abrir) — INFRA-05: compose base com Postgres 16 + Redis 7 em
  `infra/compose/docker-compose.base.yml` (volumes nomeados, network
  privada, healthchecks, portas em 127.0.0.1, Redis com `requirepass` +
  AOF, Postgres com locale `C.UTF-8`); `.env.example`, `.gitignore` local
  e `README.md` com setup, DoD e politica manual de backup (pg_dumpall +
  RDB, retencao 90d alinhada ao ADR-003). Move INFRA-05 de "Proximas
  Destravadas" para "Em Andamento". Closes #7.
- PR: (a abrir) — INFRA-04: Nginx no host + Let's Encrypt. Runbook
  `infra/nginx.md` (instalacao apt Ubuntu 24.04, webroot ACME,
  emissao SAN unico via `certbot --nginx` para apex + `www` + `app` +
  `api` + `ops`, `certbot.timer` + `certbot renew --dry-run`, HSTS so
  apos validacao). Configs versionadas em `infra/nginx/` — `nginx.conf`
  global, snippets `tls.conf` (Mozilla intermediate + stapling),
  `security-headers.conf` (HSTS comentado, X-Frame/X-Content-Type/
  Referrer/Permissions), `rate-limit.conf` (`auth_ip` 5r/s),
  `proxy-common.conf` + `connection-upgrade.conf`; server blocks
  `apex`/`www`/`app`/`api`/`ops` com placeholder "em breve" e
  `proxy_pass` comentado para 3000/8000 (INFRA-05 descomenta);
  `limit_req` em `location ^~ /auth/` do `api.conf` como prova de DoD.
  Move INFRA-04 para "Em Andamento". Move INFRA-05 para "Proximas
  Destravadas". Closes #6.
- PR: (a abrir) — DS-06: componente `<DataTable>` server-side em
  `apps/web-app/components/ui/data-table/` (TanStack Table + react-query)
  com paginacao/ordenacao/filtragem manuais, filtros texto/select/date-
  range, saved filters em localStorage, export CSV (RFC 4180 + BOM UTF-8),
  estados loading/vazio/erro+retry e preservacao de estado em
  `searchParams`. `AppQueryClientProvider` no `RootLayout`. Demo no
  `/styleguide` com 10k linhas mockadas. 23 novos testes vitest
  (csv/url-state/component). Novas deps `@tanstack/react-table` e
  `@tanstack/react-query`. Move DS-06 de "Bloqueadas" (dependia de DS-02,
  ja concluido) para "Em Andamento". Closes #45.
- PR: (a abrir) — API-04: RBAC com dependency `require_role`
  (`apps/api/api/security/rbac.py`) encadeando `assert_tenant_active`
  e devolvendo 403 claro; guarda `ensure_can_manage_member`
  protegendo owner (admin nao remove/rebaixa owner; promocao limitada
  pelo papel do ator); matriz de permissoes em
  `docs/architecture/rbac-matrix.md`; 31 testes em
  `apps/api/tests/test_rbac.py` cobrindo viewer -> 403 ao criar
  empresa via router efemero + guardas de membros. Move API-04 de
  "Bloqueadas" para "Em Andamento". Closes #28.
- PR: (a abrir) — CORE-02: refactor de `worker_core/auth.py` para aceitar
  PFX em memoria. Novo `mtls_session(pfx_bytes, pfx_password)` como
  context manager grava PEM em `/dev/shm` (fallback `tempfile.gettempdir()`)
  com `0o600` e garante cleanup em sucesso/excecao; `certificate` exposto
  em `session.nfse_certificate`. `criar_session_cliente(path, senha)`
  vira wrapper de compat (batch_processor e diagnostico intocados).
  11 novos testes em `tests/test_auth.py` com PFX gerado em memoria
  (sucesso, cleanup em excecao, senha errada, cert vencido, nao-vazamento
  em logs, tmpfs). Move CORE-02 para "Em Andamento". Closes #20.
- PR: (a abrir) — DATA-04: migrations `0006_occurrences`
  (FKs compostas para `companies` e `executions`, FK nullable para
  `users` em `assignee_user_id`, CHECKs de severity/status/ordem
  first_seen/last_seen, RLS), `0007_reprocess_jobs` (`scope jsonb`,
  `result_execution_ids text[]`, CHECK de status, RLS) e
  `0008_notifications` (`payload jsonb`, CHECKs de channel/status,
  indice parcial para pendentes, RLS) + testes estaticos. Move
  DATA-04 de "Bloqueadas" para "Em Andamento". Closes #15.
- PR: (a abrir) — DATA-05: migrations `0011_files`, `0012_schedules`,
  `0013_audit_logs` e `0014_plans_subscriptions` (sem `storage_tier`
  em `files` por ADR-003; merge dos dois heads Alembic em `0011`;
  promocao de `tenants.plan_id` a FK `-> plans.code`). RLS em `files`,
  `schedules`, `audit_logs`, `subscriptions`. Testes estaticos +
  insercao massiva (10k rows) em `audit_logs` atras de
  `TEST_DATABASE_URL`. Move DATA-05 para "Em Andamento". Closes #16.
- PR: (a abrir) — APP-01: paginas de auth (`/login`, `/signup`,
  `/recuperar-senha`, `/redefinir-senha/[token]`,
  `/aceitar-convite/[token]`) + `<AuthProvider>` com access em memoria
  e refresh automatico; Route Handlers `/api/auth/*` proxiam a API e
  guardam o refresh em cookie httpOnly; `/dashboard` protegido por
  `<RequireAuth>`; spec Playwright local; envs
  `NEXT_PUBLIC_API_BASE_URL`/`API_BASE_URL` em `config/.env.example`.
  Move APP-01 de "Bloqueadas" para "Em Andamento". Closes #49.
- PR: (a abrir) — API-03: middleware de tenant via dependencies FastAPI
  (`get_current_claims`/`assert_tenant_active`/`get_tenant_db`) em
  `apps/api/api/deps.py`, reusa `get_tenant_session` para `SET LOCAL
  app.current_tenant` sem vazamento de GUC no pool; `GET /auth/me` como
  prova de vida RLS-gated; 15 testes unitarios + 6 de integracao
  (gated por `TEST_DATABASE_URL`); runbook manual de isolamento
  cross-tenant no `apps/api/README.md`. Move API-03 para "Em Andamento".
- PR: (a abrir) — API-02: autenticacao completa em
  `apps/api/api/auth/` (signup/login/refresh/logout), argon2id, JWT
  access 15min + refresh opaco 7d com rotacao e detecao de reuso,
  migration `0010_auth_refresh_tokens` com RLS, rate limit slowapi no
  login. Move API-02 de "Proximas Destravadas" para "Em Andamento".
- PR: (a abrir) — DATA-02: migrations `0002_companies` e
  `0003_company_credentials` com RLS por tenant, unique
  `(tenant_id, cnpj)`, FK composta `(tenant_id, company_id)` e indice
  em `cert_not_after`. Tambem move DATA-01 de "Em Andamento" para
  "Concluidos" com referencia ao PR #95 (mergeado em main).
- PR: (a abrir) — DATA-03: migrations `0004_executions` (FK composta
  para `companies`, indice `(tenant_id, company_id, started_at DESC)`,
  CHECKs de trigger/status/periodo/soma, RLS) e
  `0005_execution_items` (FK composta para `executions`, indice
  unico parcial em `(tenant_id, chave_nfse)`, RLS). Move DATA-03 de
  "Proximas Destravadas" para "Em Andamento". Closes #14.
- PR: (a abrir) — INFRA-02: runbook `infra/vps-docker.md` instalando
  Docker Engine + Compose v2 pelo repo oficial, adicionando `deploy` ao
  grupo `docker`, fixando log-rotation em `/etc/docker/daemon.json` e
  criando `/srv/nfse/{prod,staging}/{data,backups,logs,config}` com
  owner `deploy:deploy` e mode `0750`. Move INFRA-02 para "Concluidos".
- PR: (a abrir) — DS-03: `<AppShell>` (sidebar colapsavel + topbar com
  breadcrumbs, tenant switcher, bell, theme toggle e user menu) e rota
  `/dashboard` consumindo o shell. Move DS-03 para "Em Andamento".
- PR: (a abrir) — DS-05: componente `KPIStatCard` com estados
  `ready`/`loading`/`empty`/`error`, delta colorido e mini-sparkline
  em SVG inline; demo com 7 cards no `/styleguide` e refactor do
  `/dashboard` para usar o componente; spec com 7 snapshots + asserts
  de acessibilidade. Closes #44.
- PR: (a abrir) — DS-04: componente `StatusBadge` com 10 variantes
  + tamanhos `sm`/`md` em `apps/web-app/components/ui/status-badge.tsx`,
  demo no `/styleguide` e primeiro spec (vitest + RTL) do `apps/web-app`
  cobrindo 20 snapshots (10 variantes x 2 tamanhos). Closes #43.
- Autor: @LevyOliveirabr
- Nota: workflow `pr-guardrail` exige STATE.md + CHANGELOG.md + `Closes #N` em todo PR para main.

## Links Rapidos

- Backlog completo: `docs/tasks/`
- Como usar os tickets: `docs/tasks/README.md`
- ADRs: `docs/adrs/`
- Contribuicao: `CONTRIBUTING.md`
