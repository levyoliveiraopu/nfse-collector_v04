# Checklist de correções — Auditoria técnica

Data de criação: 2026-06-13  
Escopo: correções e melhorias derivadas da auditoria técnica completa do repositório `nfse-collector_v04`.

## Como usar este documento

- Cada item possui um identificador estável no formato `AUDIT-XX`.
- Atualize o status conforme o andamento:
  - `[ ]` Pendente
  - `[~]` Em andamento
  - `[x]` Corrigido
  - `[!]` Bloqueado por decisão, credencial, infraestrutura ou validação manual
- Ao corrigir um item, registre:
  1. PR/commit da correção;
  2. arquivos alterados;
  3. testes executados;
  4. evidência objetiva do resultado.
- Não marque item como `[x]` sem evidência reproduzível.
- Prioridade sugerida:
  - `P0`: bloqueia execução, CI, segurança crítica ou produção;
  - `P1`: alto risco operacional, integridade ou confiabilidade;
  - `P2`: melhoria importante de manutenção, produto ou DevEx;
  - `P3`: evolução futura/estratégica.

---

## P0 — Correções bloqueantes

### AUDIT-01 — Corrigir erro de sintaxe da API

- Status: [ ] Pendente
- Prioridade: P0
- Onde: `apps/api/api/config.py`, método `_validate_auth_secrets`.
- Problema: existe um `if` duplicado sem bloco, causando `IndentationError`.
- Impacto: a API não importa, não sobe e os testes de API não coletam.
- Correção proposta:
  - Remover o `if` incompleto;
  - Manter a validação de `API_JWT_SECRET` com mínimo de 32 bytes em staging/production;
  - Rodar `python -m py_compile apps/api/api/config.py`.
- Evidência esperada:
  - `python -m py_compile apps/api/api/config.py` passando;
  - `ruff check .` sem erro de sintaxe.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

### AUDIT-02 — Restaurar a suíte de testes da API

- Status: [ ] Pendente
- Prioridade: P0
- Onde: `apps/api/tests`.
- Problema: a suíte falha durante a coleta por causa do erro em `config.py`.
- Impacto: não há garantia de auth, RLS, storage, migrations, executions e demais rotas da API.
- Correção proposta:
  - Corrigir `AUDIT-01`;
  - Rodar `python -m pytest apps/api/tests -q`;
  - Corrigir falhas reais remanescentes, se aparecerem.
- Evidência esperada:
  - Saída completa do pytest com testes passando ou lista documentada de testes bloqueados por `TEST_DATABASE_URL`.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

### AUDIT-03 — Corrigir falha de lint por teste duplicado

- Status: [ ] Pendente
- Prioridade: P0
- Onde: `tests/test_jobs.py`.
- Problema: `test_run_execution_dry_run_nao_grava_items_nem_upload` está definido duas vezes.
- Impacto: uma definição sobrescreve a outra e o `ruff check .` falha com `F811`.
- Correção proposta:
  - Remover duplicação ou transformar os casos em teste parametrizado;
  - Garantir que o comportamento de dry-run continue coberto.
- Evidência esperada:
  - `ruff check .` passando;
  - `python -m pytest tests/test_jobs.py -q` passando.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

### AUDIT-04 — Garantir gate de CI verde antes de qualquer deploy

- Status: [ ] Pendente
- Prioridade: P0
- Onde: `.github/workflows/ci.yml`, comandos locais de validação e branch protection.
- Problema: o branch atual contém falhas que deveriam bloquear merge/deploy.
- Impacto: risco de publicar imagem quebrada ou código que não inicia.
- Correção proposta:
  - Rodar localmente todos os comandos do CI;
  - Confirmar branch protection exigindo CI verde;
  - Registrar evidências no PR.
- Evidência esperada:
  - `ruff check .` passando;
  - `python -m pytest tests apps/api/tests apps/worker/tests -q` passando ou com bloqueios documentados;
  - `pnpm --filter web-app typecheck` passando;
  - `pnpm --filter web-app test` passando.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

---

## P1 — Integridade operacional e segurança

### AUDIT-05 — Evitar enqueue antes do commit em `POST /executions`

- Status: [ ] Pendente
- Prioridade: P1
- Onde: `apps/api/api/executions/routes.py` e camada de fila.
- Problema: a API enfileira jobs enquanto a transação de criação da execution ainda não foi confirmada.
- Impacto: o worker pode consumir o job antes de a linha existir de forma visível, retornando `not_found` ou deixando execução órfã.
- Correção proposta:
  - Preferencial: implementar outbox transacional de jobs;
  - Alternativa mínima: usar transação explícita, confirmar inserts e só então enfileirar;
  - Garantir tratamento de falha de enqueue pós-commit.
- Evidência esperada:
  - Teste unitário/integrado simulando worker rápido;
  - Execução criada só é enfileirada após commit confirmável.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

### AUDIT-06 — Evitar enqueue antes do commit no scheduler

- Status: [ ] Pendente
- Prioridade: P1
- Onde: `apps/worker/worker/scheduler.py`.
- Problema: o scheduler insere execution e enfileira job dentro da mesma transação tenant.
- Impacto: mesma corrida do `AUDIT-05`, agora em execuções agendadas.
- Correção proposta:
  - Aplicar o mesmo padrão escolhido para `AUDIT-05`;
  - Cobrir scheduler com teste de commit-before-enqueue ou outbox.
- Evidência esperada:
  - Teste de scheduler validando que jobs não são enfileirados antes de a execution estar persistida.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

### AUDIT-07 — Proteger rotação de refresh token contra concorrência

- Status: [ ] Pendente
- Prioridade: P1
- Onde: `apps/api/api/security/tokens.py`.
- Problema: `rotate_refresh_token` faz `SELECT` seguido de insert/update sem lock explícito.
- Impacto: duas requisições simultâneas podem criar cadeias inconsistentes de refresh token.
- Correção proposta:
  - Usar `SELECT ... FOR UPDATE` no refresh token atual;
  - Garantir que apenas uma rotação vença;
  - Criar teste concorrente ou teste SQL que comprove o lock.
- Evidência esperada:
  - Teste cobrindo duas rotações simultâneas;
  - Reuso do token antigo revogando cadeia corretamente.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

### AUDIT-08 — Consolidar idempotência forte de execuções abertas

- Status: [ ] Pendente
- Prioridade: P1
- Onde: `apps/api/api/executions/routes.py`, migrations de `executions` e scheduler.
- Problema: existe pré-check de execução aberta, mas sem garantia forte no banco contra corrida concorrente.
- Impacto: múltiplos requests/schedulers podem duplicar trabalho para a mesma empresa/janela.
- Correção proposta:
  - Usar advisory lock por tenant/company/janela; ou
  - Criar índice único parcial compatível com o domínio; ou
  - Centralizar idempotência em tabela/outbox.
- Evidência esperada:
  - Teste de concorrência provando que apenas uma execution aberta equivalente é criada.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

### AUDIT-09 — Clarificar e separar roles de banco do worker

- Status: [ ] Pendente
- Prioridade: P1
- Onde: `config/.env.example`, `worker_core.db`, jobs de export/coleta e docs de deploy.
- Problema: documentação sugere `app_admin` e `app_user` para `WORKER_DATABASE_URL` em pontos diferentes.
- Impacto: risco de permissões excessivas ou falha operacional por role incompatível.
- Correção proposta:
  - Definir claramente quais jobs precisam de admin e quais rodam com RLS;
  - Separar variáveis se necessário (`WORKER_ADMIN_DATABASE_URL`, `WORKER_DATABASE_URL`);
  - Atualizar docs e Compose.
- Evidência esperada:
  - Documentação sem contradição;
  - Testes ou smoke comprovando worker/export com as roles escolhidas.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

### AUDIT-10 — Adicionar proteção CSRF/Origin nas rotas locais de sessão

- Status: [ ] Pendente
- Prioridade: P1
- Onde: `apps/web-app/app/api/auth/*` e `apps/web-app/lib/auth/server.ts`.
- Problema: refresh/logout usam cookie httpOnly e não há validação explícita de Origin/CSRF.
- Impacto: risco moderado em cenários de requisições cross-site, mesmo com `SameSite=Lax`.
- Correção proposta:
  - Validar `Origin`/`Referer` em métodos mutantes;
  - Opcionalmente adicionar token CSRF para ações sensíveis;
  - Cobrir com testes dos route handlers.
- Evidência esperada:
  - Requisição com Origin inválida rejeitada;
  - Fluxos normais de login/refresh/logout continuam funcionando.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

---

## P2 — Produto, DevEx e manutenção

### AUDIT-11 — Implementar ou ocultar a gestão real de usuários

- Status: [ ] Pendente
- Prioridade: P2
- Onde: `apps/web-app/app/usuarios`, `apps/web-app/lib/users/api-client.ts`, backend API.
- Problema: frontend consome endpoints `/tenant/*` ainda não implementados na API.
- Impacto: página `/usuarios` tende a falhar em produção.
- Correção proposta:
  - Implementar backend real de members/invitations; ou
  - Ocultar rota/CTA até o backend existir;
  - Ajustar README para não afirmar CRUD de users se ainda não existir.
- Evidência esperada:
  - Testes de integração backend;
  - Testes frontend contra contrato real;
  - Fluxo de convite/remover/alterar papel validado.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

### AUDIT-12 — Substituir assinatura mockada por endpoint real ou feature flag

- Status: [ ] Pendente
- Prioridade: P2
- Onde: `apps/web-app/lib/subscription/mock.ts`, página `/assinatura`, backend de billing/usage.
- Problema: a página exibe dados fixos de assinatura e uso.
- Impacto: usuário pode interpretar dados falsos como reais.
- Correção proposta:
  - Criar endpoint real de subscription/usage; ou
  - Marcar visualmente como demo/indisponível e esconder em produção;
  - Implementar enforcement de limites quando billing entrar no escopo.
- Evidência esperada:
  - Dados de uso refletindo tenant real;
  - Testes cobrindo limites e estados de plano.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

### AUDIT-13 — Criar lockfile/constraints para dependências Python

- Status: [ ] Pendente
- Prioridade: P2
- Onde: `requirements.txt`, `apps/*/pyproject.toml`, `packages/worker-core/pyproject.toml`.
- Problema: dependências Python usam versões abertas ou sem pin.
- Impacto: builds não reprodutíveis, risco de quebra por atualização indireta e dificuldade de responder a CVEs.
- Correção proposta:
  - Adotar `uv.lock`, `pip-tools` ou constraints versionadas;
  - Atualizar CI para instalar a partir do lock/constraints;
  - Adicionar rotina de audit/dependabot.
- Evidência esperada:
  - Instalação reprodutível em ambiente limpo;
  - CI usando lock/constraints.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

### AUDIT-14 — Remover código morto em `run_execution`

- Status: [ ] Pendente
- Prioridade: P2
- Onde: `packages/worker-core/worker_core/jobs.py`.
- Problema: há bloco inatingível após `raise JobError(...)` no tratamento de erro do portal.
- Impacto: confunde manutenção e pode esconder intenção antiga de classificação de erro.
- Correção proposta:
  - Remover bloco morto;
  - Garantir que classificação de mTLS/portal continue coberta por testes.
- Evidência esperada:
  - Testes de jobs passando;
  - Cobertura explícita para `ValueError`, timeout, connection error, 5xx e rate limit.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

### AUDIT-15 — Centralizar queries SQL críticas

- Status: [ ] Pendente
- Prioridade: P2
- Onde: rotas API, worker jobs e scheduler.
- Problema: SQL textual está espalhado por handlers e jobs.
- Impacto: manutenção difícil, risco de divergência de contrato e refactors caros.
- Correção proposta:
  - Criar módulos de repositório por domínio;
  - Padronizar helpers para paginação, inserts idempotentes, auditoria e ocorrências;
  - Manter SQL explícito onde fizer sentido, mas centralizado.
- Evidência esperada:
  - Redução de duplicidade;
  - Testes de contrato por repositório.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

### AUDIT-16 — Atualizar documentação de status do README

- Status: [ ] Pendente
- Prioridade: P2
- Onde: `README.md`, `STATE.md`, documentação de produção.
- Problema: README afirma funcionalidades que estão parcialmente pendentes ou mockadas.
- Impacto: cria expectativa errada para novo desenvolvedor/operador.
- Correção proposta:
  - Separar “funcional”, “parcial”, “mockado” e “bloqueado por validação manual”;
  - Referenciar este checklist.
- Evidência esperada:
  - README alinhado ao estado real após correções.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

---

## P3 — Evoluções estratégicas

### AUDIT-17 — Implementar outbox transacional genérica

- Status: [ ] Pendente
- Prioridade: P3
- Onde: API, worker, migrations e fila Redis/RQ.
- Problema: jobs e notificações são parcialmente acoplados ao fluxo síncrono da request.
- Impacto: retry, idempotência e observabilidade ficam mais difíceis.
- Correção proposta:
  - Criar tabela `outbox_events` ou `job_outbox`;
  - Dispatcher separado publica em Redis/RQ;
  - Marcar eventos como publicados/falhos com retry/backoff.
- Evidência esperada:
  - Teste integrado garantindo atomicidade DB + evento.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

### AUDIT-18 — Melhorar exportação ZIP para alto volume

- Status: [ ] Pendente
- Prioridade: P3
- Onde: `packages/worker-core/worker_core/jobs.py`, storage e API de exports.
- Problema: ZIP é montado em tmpfs/local com limite de 2 GiB.
- Impacto: tenants com alto volume podem bater limite de RAM/disco/tempo.
- Correção proposta:
  - Avaliar streaming zip, particionamento por período ou exports paginados;
  - Adicionar estimativa prévia e UX para volume grande.
- Evidência esperada:
  - Teste com volume grande simulado;
  - Métricas de tempo/tamanho.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

### AUDIT-19 — Criar métricas operacionais de fila e execuções

- Status: [ ] Pendente
- Prioridade: P3
- Onde: API, worker, scheduler, Grafana/Loki/Uptime Kuma.
- Problema: observabilidade documentada existe, mas precisa ser validada no ambiente real.
- Impacto: incidentes de fila parada, scheduler sem tick ou taxa alta de erro podem demorar a ser detectados.
- Correção proposta:
  - Métricas de jobs queued/running/failed, idade do job mais antigo, execuções por status e erro por código;
  - Alertas com runbook vinculado.
- Evidência esperada:
  - Dashboard validado em staging;
  - Simulação de incidente registrada.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

### AUDIT-20 — Criar smoke E2E pós-deploy

- Status: [ ] Pendente
- Prioridade: P3
- Onde: CI/CD, Playwright, API, worker, Redis, Postgres e S3 staging.
- Problema: há testes unitários e integração parcial, mas falta smoke ponta a ponta real de ambiente.
- Impacto: deploy pode estar verde em testes isolados e falhar no fluxo real.
- Correção proposta:
  - Rodar fluxo mínimo: signup/login, criar empresa, credencial fake/stub ou real de staging, criar execution, worker processar, listar arquivos/ocorrências;
  - Separar testes que exigem secrets reais.
- Evidência esperada:
  - Job de smoke pós-deploy com logs e status final.
- PR/commit:
- Arquivos alterados:
- Testes executados:
- Observações:

---

## Quadro de acompanhamento rápido

| ID | Prioridade | Status | Resumo | Dono | PR/commit |
|----|------------|--------|--------|------|-----------|
| AUDIT-01 | P0 | [ ] | Corrigir erro de sintaxe da API | | |
| AUDIT-02 | P0 | [ ] | Restaurar testes da API | | |
| AUDIT-03 | P0 | [ ] | Corrigir teste duplicado/lint | | |
| AUDIT-04 | P0 | [ ] | Garantir CI verde | | |
| AUDIT-05 | P1 | [ ] | Enqueue após commit na API | | |
| AUDIT-06 | P1 | [ ] | Enqueue após commit no scheduler | | |
| AUDIT-07 | P1 | [ ] | Lock na rotação de refresh token | | |
| AUDIT-08 | P1 | [ ] | Idempotência forte de execuções | | |
| AUDIT-09 | P1 | [ ] | Separar/clarificar roles do worker | | |
| AUDIT-10 | P1 | [ ] | CSRF/Origin em rotas de sessão | | |
| AUDIT-11 | P2 | [ ] | Usuários: backend real ou ocultar UI | | |
| AUDIT-12 | P2 | [ ] | Assinatura: endpoint real ou flag | | |
| AUDIT-13 | P2 | [ ] | Lockfile/constraints Python | | |
| AUDIT-14 | P2 | [ ] | Remover código morto do worker | | |
| AUDIT-15 | P2 | [ ] | Centralizar SQL crítico | | |
| AUDIT-16 | P2 | [ ] | Atualizar documentação de status | | |
| AUDIT-17 | P3 | [ ] | Outbox transacional genérica | | |
| AUDIT-18 | P3 | [ ] | Export ZIP para alto volume | | |
| AUDIT-19 | P3 | [ ] | Métricas operacionais reais | | |
| AUDIT-20 | P3 | [ ] | Smoke E2E pós-deploy | | |
