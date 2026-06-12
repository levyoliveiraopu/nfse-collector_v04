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

- [ ] Publicar imagem Docker da API.
  - Status atual: existe `apps/api/Dockerfile` e workflow publica `nfse-api`.
- [ ] Criar/publicar imagem Docker do worker.
  - Resultado esperado: imagem `nfse-worker` com entrypoints `nfse-worker` e `nfse-scheduler`.
- [ ] Criar/publicar imagem Docker do web-app.
  - Resultado esperado: imagem `nfse-web-app` com build Next.js e start em porta interna.
- [ ] Ativar servico `worker` no compose de deploy.
- [ ] Ativar servico `scheduler` no compose de deploy.
- [ ] Ativar servico `web-app` no compose de deploy.
- [ ] Adicionar healthcheck para API, worker, scheduler e web-app.

## 2.2 Migrations e release

- [ ] Rodar `alembic upgrade head` automaticamente no deploy.
  - Motivo: imagem nova nao pode subir contra schema antigo.
- [ ] Criar procedimento de rollback que considere migrations.
  - Motivo: rollback de imagem sem rollback/compatibilidade de schema pode quebrar.
- [ ] Separar `/health` de `/ready`.
  - `/health`: processo vivo.
  - `/ready`: DB, Redis e configuracoes essenciais acessiveis.
- [ ] Healthcheck de deploy deve validar `/ready`, nao apenas `/health`.

## 2.3 VPS, DNS, TLS e Nginx

- [!] Provisionar VPS com Docker, usuario `deploy`, firewall e diretorios `/srv/nfse/<env>`.
- [!] Configurar secrets GitHub Actions: `SSH_HOST`, `SSH_USER`, `SSH_KEY` e, se necessario, `GHCR_TOKEN`.
- [!] Configurar dominios definitivos para apex/www/app/api/ops.
- [!] Emitir TLS com Let's Encrypt.
- [ ] Descomentar/apontar `proxy_pass` nos server blocks de app/api.
- [ ] Validar headers de seguranca e rate limit no Nginx.

## 2.4 Storage S3/B2

- [!] Criar bucket S3/B2 real.
- [!] Configurar `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_KEY_ID`, `S3_APPLICATION_KEY`.
- [ ] Validar lifecycle: XMLs/artefatos derivados com retencao correta e credenciais fora de lifecycle destrutivo.
- [ ] Executar smoke test real de upload, presigned URL e delete.
- [ ] Validar politicas de permissao minima do bucket.

## 2.5 Banco e Redis

- [ ] Definir roles/conexoes separadas para admin/migrations e app_user quando aplicavel.
- [ ] Confirmar RLS ativa e `FORCE ROW LEVEL SECURITY` nas tabelas tenant-scoped.
- [ ] Configurar backup diario criptografado do Postgres.
- [ ] Executar drill de restore antes de producao.
- [ ] Configurar Redis com senha, AOF e persistencia adequada.

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
