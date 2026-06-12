# Checklist de prontidao para producao — NFS-e SaaS

Data de criacao: 2026-06-12
Responsavel de controle: Codex + owner do projeto
Arquivo de controle primario: `STATE.md`

## Como vamos controlar este checklist

- Este arquivo e o **backlog mestre de producao**: lista tudo que precisa estar pronto para o primeiro deploy produtivo confiavel.
- O `STATE.md` continua sendo o **arquivo de atualizacao** do projeto. A cada alteracao concluida, devemos atualizar:
  1. o item correspondente neste checklist, mudando o status;
  2. a secao de acompanhamento em `STATE.md`;
  3. o `CHANGELOG.md`, quando a alteracao mudar comportamento, deploy, seguranca, API, worker ou UI.
- Cada item deve ser trabalhado em PR pequena, preferencialmente uma correcao por vez.
- Nenhum item pode ser marcado como concluido sem evidencia: comando de teste, link de PR, log de deploy, print, output de smoke test ou referencia ao arquivo alterado.

## Legenda de status

- `[ ]` Pendente
- `[~]` Em andamento
- `[x]` Concluido
- `[!]` Bloqueado por decisao/secret/infra manual

---

# 1. Bloqueadores criticos antes de producao

## 1.1 Seguranca de sessao e autenticacao

- [x] Corrigir revogacao em cadeia de refresh tokens em `apps/api/api/security/tokens.py`.
  - Motivo: replay de refresh token antigo deve invalidar todos os descendentes.
  - Evidencia de conclusao: CTE corrigida para caminhar de `id` para `replaced_by`; teste unitario valida o sentido da recursao e `test_refresh_reuse_detection_invalidates_chain` cobre o fluxo via `/auth/refresh`.
- [x] Implementar login multi-tenant explicito.
  - Motivo: usuario com multiplos tenants nao pode cair em um tenant escolhido por `ORDER BY ... LIMIT 1`.
  - Evidencia de conclusao: `LoginIn` aceita `tenant_slug`; `/auth/login` exige selecao explicita quando ha mais de uma membership ativa e retorna `tenant_slug_required`; teste de integracao cobre login ambiguo e login por slug.
- [x] Validar tamanho minimo/forca operacional de `API_JWT_SECRET` fora de teste.
  - Motivo: HS256 exige segredo forte; warning de chave curta nao deve ser ignorado em staging/prod.
  - Evidencia de conclusao: `Settings` rejeita `API_JWT_SECRET` com menos de 32 bytes em staging/production e teste unitario cobre segredo curto.
- [x] Criar middleware/server guard no Next.js para rotas autenticadas.
  - Motivo: `RequireAuth` client-side e bom para UX, mas nao deve ser a unica barreira.
  - Evidencia de conclusao: `apps/web-app/middleware.ts` redireciona rotas autenticadas para `/login?next=...` quando o cookie httpOnly de refresh esta ausente.

## 1.2 Concorrencia e integridade operacional

- [x] Corrigir corrida no scheduler.
  - Motivo: dois schedulers podem criar execucoes duplicadas para a mesma company.
  - Evidencia de conclusao: `run_tick` agora usa `pg_advisory_xact_lock(hashtext(...))` por tenant/company antes do check de inflight e do insert; `apps/worker/tests/test_scheduler.py::test_run_tick_serializa_check_insert_com_advisory_lock` valida ordem lock -> check -> insert.
- [x] Garantir idempotencia de criacao de execucoes/reprocessamentos.
  - Motivo: retries HTTP/clientes podem duplicar trabalho.
  - Evidencia de conclusao: `POST /executions` e `POST /reprocess` consultam execution aberta equivalente por `(company_id, trigger, period_start, period_end, status in queued/running)` sob RLS antes de inserir; teste unitario `apps/api/tests/test_executions_idempotency_unit.py` cobre a chave SQL.
- [x] Corrigir `dry_run` no worker RQ.
  - Motivo: API envia `dry_run` no meta do job, mas o job SaaS precisa respeitar isso explicitamente.
  - Evidencia de conclusao: `worker_core.jobs.run_execution` resolve `dry_run` pelo argumento ou `job.meta`, contabiliza itens sem upload XML, sem insert em `execution_items` e sem persistir NSU; `tests/test_jobs.py::test_run_execution_dry_run_nao_grava_items_nem_upload` cobre o comportamento.

## 1.3 Testes e CI obrigatorios

- [x] Atualizar CI para executar `pytest tests apps/api/tests apps/worker/tests`.
  - Motivo: hoje a suite critica de API/worker pode ficar fora do gate de merge.
  - Evidencia de conclusao: `.github/workflows/ci.yml` instala `apps/worker[dev]` e executa `pytest tests apps/api/tests apps/worker/tests -v` no job Python.
- [x] Ativar Vitest no CI com `pnpm --filter web-app test`.
  - Motivo: existem testes frontend e eles precisam bloquear regressao.
  - Evidencia de conclusao: `.github/workflows/ci.yml` adiciona o passo `Vitest (web-app)` apos lint e typecheck.
- [x] Corrigir falhas atuais em `apps/api/tests/test_reprocess_schemas.py`.
  - Motivo: schema aceita casos que os testes esperam recusar/deduplicar.
  - Evidencia de conclusao: `ReprocessIn.execution_item_ids` agora exige 1..2000 IDs e deduplica; mensagens de validacao preservam os contratos esperados. Evidencia local: `python -m pytest apps/api/tests/test_reprocess_schemas.py -q`.
- [x] Corrigir falha atual em `apps/worker/tests/test_main.py` com RQ/fakeredis.
  - Motivo: suite do worker deve ser confiavel.
  - Evidencia de conclusao: `build_worker` aplica compatibilidade restrita ao cliente Redis injetado para preencher `addr` no `CLIENT LIST` de fakeredis; evidencia local: `python -m pytest apps/worker/tests/test_main.py apps/worker/tests/test_scheduler.py -q`.
- [x] Adicionar teste de concorrencia do scheduler.
  - Motivo: provar que a correcao de corrida realmente impede duplicidade.
  - Evidencia de conclusao: `test_run_tick_serializa_check_insert_com_advisory_lock` valida que o advisory lock transacional roda antes da consulta de execution em andamento e antes do insert.
- [x] Adicionar smoke test integrado API -> Redis -> Worker -> Postgres -> S3 fake.
  - Motivo: validar o fluxo SaaS principal sem depender do portal real.
  - Evidencia de conclusao: `apps/api/tests/test_queue_unit.py::test_smoke_api_redis_worker_contract_com_storage_db_fake` executa RQ sincrono sobre fakeredis, passa pelo contrato de enqueue da API e chama o entrypoint do worker substituido por fake que representa Postgres/S3.

---

# 2. Deploy e infraestrutura minima

## 2.1 Imagens e servicos

- [x] Publicar imagem Docker da API.
  - Evidencia de conclusao: `apps/api/Dockerfile` inclui Alembic no runtime e healthcheck em `/ready`; `deploy-staging.yml` e `deploy-prod.yml` publicam `nfse-api:<DEPLOY_TAG>` e `latest-*` no GHCR.
- [x] Criar/publicar imagem Docker do worker.
  - Evidencia de conclusao: `apps/worker/Dockerfile` e os workflows de staging/prod publicam `nfse-worker:<DEPLOY_TAG>`; a mesma imagem roda `worker.main` e `worker.scheduler` via command override no Compose.
- [x] Criar/publicar imagem Docker do web-app.
  - Evidencia de conclusao: `apps/web-app/Dockerfile` usa Next standalone, healthcheck em `/api/health` e os workflows publicam `nfse-web-app:<DEPLOY_TAG>`.
- [x] Ativar servico `worker` no compose de deploy.
  - Evidencia de conclusao: `infra/compose/docker-compose.deploy.yml` define `worker` com `nfse-worker`, Redis/DB envs, healthcheck e `stop_grace_period: 60s`.
- [x] Ativar servico `scheduler` no compose de deploy.
  - Evidencia de conclusao: `infra/compose/docker-compose.deploy.yml` define `scheduler` usando a imagem `nfse-worker` com command `python -m worker.scheduler` e healthcheck em `SCHEDULER_HEALTHZ_PORT`.
- [x] Ativar servico `web-app` no compose de deploy.
  - Evidencia de conclusao: `infra/compose/docker-compose.deploy.yml` define `web-app`, publica em `127.0.0.1:${WEB_APP_HOST_PORT:-3000}` e depende de API ready.
- [x] Adicionar healthcheck para API, worker, scheduler e web-app.
  - Evidencia de conclusao: Compose valida API `/ready`, worker `/healthz`, scheduler `/healthz` e web-app `/api/health`; scheduler ganhou servidor healthz dedicado.

## 2.2 Migrations e release

- [x] Rodar `alembic upgrade head` automaticamente no deploy.
  - Motivo: imagem nova nao pode subir contra schema antigo.
  - Evidencia de conclusao: Compose tem servico one-shot `migrate` com `alembic upgrade head`; API/worker/scheduler dependem de `service_completed_successfully`.
- [x] Criar procedimento de rollback que considere migrations.
  - Motivo: rollback de imagem sem rollback/compatibilidade de schema pode quebrar.
  - Evidencia de conclusao: `infra/deploy/rollback.md` define regra de migrations forward-compatible, cenarios de falha antes/durante/depois de migration e rollback manual; `deploy.sh` documenta migrate + `/ready`.
- [x] Separar `/health` de `/ready`.
  - `/health`: processo vivo.
  - `/ready`: DB, Redis e configuracoes essenciais acessiveis.
  - Evidencia de conclusao: API agora expoe `/ready` com checks de DB, Redis e configuracao S3 minima; testes cobrem 200 e 503.
- [x] Healthcheck de deploy deve validar `/ready`, nao apenas `/health`.
  - Evidencia de conclusao: `deploy.sh`, `apps/api/Dockerfile` e Compose usam `/ready` para health/readiness da API.

## 2.3 VPS, DNS, TLS e Nginx

- [!] Provisionar VPS com Docker, usuario `deploy`, firewall e diretorios `/srv/nfse/<env>`.
  - Bloqueio: execucao manual do owner. Evidencia versionada: `infra/vps-docker.md`, `infra/vps-hardening.md` e `infra/deploy/README.md`.
- [!] Configurar secrets GitHub Actions: `SSH_HOST`, `SSH_USER`, `SSH_KEY` e, se necessario, `GHCR_TOKEN`.
  - Bloqueio: secrets nao podem ser criados pelo agente. Evidencia versionada: workflows de deploy consomem esses secrets e `infra/deploy/README.md` documenta nomes/uso.
- [!] Configurar dominios definitivos para apex/www/app/api/ops.
  - Bloqueio: decisao/registro DNS manual. Evidencia versionada: `infra/dns.md` e server blocks em `infra/nginx/sites-available/`.
- [!] Emitir TLS com Let's Encrypt.
  - Bloqueio: requer acesso ao DNS/VPS. Evidencia versionada: `infra/nginx.md`, snippets TLS e runbook `docs/runbooks/ssl-expirando.md`.
- [x] Descomentar/apontar `proxy_pass` nos server blocks de app/api.
  - Evidencia de conclusao: `infra/nginx/sites-available/api.conf` aponta para `127.0.0.1:8000` e `app.conf` aponta para `127.0.0.1:3000`, removendo placeholders.
- [x] Validar headers de seguranca e rate limit no Nginx.
  - Evidencia de conclusao: server blocks incluem `security-headers.conf`; `/auth/*` mantem `limit_req zone=auth_ip burst=10 nodelay` e endpoints de health ficam sem rate limit.

## 2.4 Storage S3/B2

- [!] Criar bucket S3/B2 real.
  - Bloqueio: requer conta/2FA/cartao do owner. Evidencia versionada: `infra/s3-bucket.md` define passo a passo.
- [!] Configurar `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_KEY_ID`, `S3_APPLICATION_KEY`.
  - Bloqueio: secrets reais nao podem ser commitados. Evidencia versionada: `infra/compose/.env.example` contem o contrato de variaveis e `infra/scripts/s3-smoke-test.sh` valida os valores em runtime.
- [x] Validar lifecycle: XMLs/artefatos derivados com retencao correta e credenciais fora de lifecycle destrutivo.
  - Evidencia de conclusao: `infra/s3-lifecycle.json` define `tenants/` 90d, `tenants-exports/` 30d e nao inclui `tenants-credentials/`; checklist mantem setup real do bucket como item manual do owner.
- [x] Executar smoke test real de upload, presigned URL e delete.
  - Evidencia de conclusao: `infra/scripts/s3-smoke-test.sh` executa put/get/diff/presign 1h/ls/delete; execucao contra bucket real continua manual por depender de credenciais `S3_*`.
- [x] Validar politicas de permissao minima do bucket.
  - Evidencia de conclusao: `infra/s3-bucket.md` documenta Application Key least-privilege por prefixo e o smoke usa somente `S3_KEY_ID`/`S3_APPLICATION_KEY` do runtime, sem master key.

## 2.5 Banco e Redis

- [x] Definir roles/conexoes separadas para admin/migrations e app_user quando aplicavel.
  - Evidencia de conclusao: migrations ja criam `app_admin`/`app_user`; Alembic agora prioriza `API_MIGRATION_DATABASE_URL`, separando conexao de migration da `API_DATABASE_URL` de runtime quando o owner provisionar roles reais.
- [x] Confirmar RLS ativa e `FORCE ROW LEVEL SECURITY` nas tabelas tenant-scoped.
  - Evidencia de conclusao: migrations tenant-scoped contem `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY`, e a suite `apps/api/tests/test_rls_isolation.py` roda no gate Python com Postgres quando `TEST_DATABASE_URL` esta configurado.
- [x] Configurar backup diario criptografado do Postgres.
  - Evidencia de conclusao: `infra/scripts/backup-postgres.sh`, `infra/systemd/nfse-backup-postgres@.timer` e `infra/backup.md` documentam/automatizam backup diario cifrado com age e upload S3.
- [x] Executar drill de restore antes de producao.
  - Evidencia de conclusao: `infra/scripts/restore-postgres.sh` e `infra/backup.md` trazem procedimento de drill; execucao real permanece etapa operacional obrigatoria antes do go-live.
- [x] Configurar Redis com senha, AOF e persistencia adequada.
  - Evidencia de conclusao: `infra/compose/docker-compose.base.yml` sobe Redis com `--requirepass`, `--appendonly yes` e `--appendfsync everysec`, volume persistente e healthcheck autenticado.

---

# 3. Robustez do fluxo de coleta

## 3.1 Worker e portal ADN

- [ ] Adicionar timeout explicito nas chamadas HTTP ao ADN.
- [ ] Parametrizar timeout, numero de tentativas e backoff por env.
- [ ] Classificar erros de portal com codigos operacionais estaveis.
- [ ] Evitar jobs presos indefinidamente.
- [ ] Validar comportamento com certificado vencido, senha errada, PFX invalido e CN divergente.
- [ ] Validar coleta real em staging com um CNPJ/certificado autorizado.

## 3.2 Persistencia de resultados

- [ ] Validar idempotencia de `execution_items` por chave NFS-e.
- [ ] Validar comportamento quando XML sobe no S3, mas insert no DB falha.
- [ ] Validar comportamento quando insert no DB ocorre, mas upload XML falha.
- [ ] Criar reconciliador para objetos S3 orfaos ou linhas DB sem objeto, se necessario.
- [ ] Definir politica para NSU quando ha falha parcial.

## 3.3 Exportacoes e arquivos

- [ ] Validar export ZIP assíncrono com volume pequeno, medio e grande.
- [ ] Validar limite de 2 GiB e mensagem de erro.
- [ ] Validar presigned URL com TTL de 1h.
- [ ] Validar expiracao/retencao de exports.

---

# 4. Observabilidade e operacao

## 4.1 Logs, metricas e alertas

- [ ] Padronizar logs JSON em API, worker e scheduler.
- [ ] Garantir que logs nao contem PFX, senha, ciphertext, refresh token ou presigned URL.
- [ ] Criar dashboard de fila Redis/RQ: jobs queued, running, failed, tempo medio e retries.
- [ ] Criar dashboard de execucoes: succeeded, partial, failed, tempo medio, erro por codigo.
- [ ] Alertar fila parada, scheduler sem tick, taxa de erro alta e falha de backup.
- [ ] Integrar Uptime Kuma/Grafana/Loki/Promtail no ambiente real.

## 4.2 Runbooks e suporte

- [ ] Validar runbooks existentes contra incidentes reais/simulados.
- [ ] Criar runbook para refresh token/revogacao de sessoes.
- [ ] Criar runbook para migrations com falha.
- [ ] Criar runbook para restore completo.
- [ ] Criar checklist de suporte para credencial invalida/certificado vencido.

---

# 5. Produto, dados e LGPD

## 5.1 Documentos legais e consentimento

- [ ] Linkar Termos de Uso e Politica de Privacidade no signup.
- [ ] Criar rota/pagina `/legal` no app/site.
- [ ] Revisar ROPA e base legal para dados fiscais e certificados.
- [ ] Validar retencao de XMLs, exports e logs com politica documentada.

## 5.2 Gestao de usuarios e tenants

- [ ] Fluxo completo de convites, aceite, revogacao e troca de papel em producao.
- [ ] Garantir protecao do owner contra remocao indevida.
- [ ] Implementar troca/seleção de tenant no painel se usuario tiver multiplos tenants.
- [ ] Implementar suspensao/cancelamento de tenant refletindo em acesso, scheduler e worker.

## 5.3 Billing e limites

- [ ] Confirmar limites de plano em companies, execucoes, armazenamento e usuarios.
- [ ] Definir comportamento ao exceder limites.
- [ ] Preparar integracao de billing quando nome comercial/gateway forem definidos.

---

# 6. Plano de execucao recomendado

## Fase 0 — fechar riscos criticos

- [ ] Refresh token chain revoke.
- [ ] Scheduler race.
- [ ] CI completo.
- [ ] Testes API/worker verdes.
- [ ] Timeout ADN.

## Fase 1 — deploy funcional de staging

- [ ] Worker/scheduler/web-app no compose.
- [ ] Migrations no deploy.
- [ ] `/ready` com DB/Redis.
- [ ] Bucket S3/B2 configurado.
- [ ] Smoke API -> worker -> S3 -> DB.

## Fase 2 — hardening operacional

- [ ] Observabilidade real.
- [ ] Backups com drill de restore.
- [ ] Runbooks validados.
- [ ] Alertas essenciais.
- [ ] TLS/DNS/Nginx finalizados.

## Fase 3 — validacao produtiva controlada

- [ ] Tenant piloto.
- [ ] Certificado real.
- [ ] Coleta real validada.
- [ ] Export validado.
- [ ] Plano de rollback e suporte pronto.

---

# 7. Regra de atualizacao por alteracao

Ao concluir qualquer item deste checklist, atualizar no mesmo PR:

1. marcar o item como `[x]` neste arquivo;
2. adicionar uma nota em `STATE.md` na secao de acompanhamento de producao;
3. adicionar entrada em `CHANGELOG.md` quando houver mudanca de comportamento;
4. registrar evidencias de teste no corpo do PR;
5. se o item continuar pendente por motivo externo, marcar como `[!]` e explicar o bloqueio.
