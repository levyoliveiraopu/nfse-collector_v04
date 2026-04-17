# Runbook — falha de storage (S3/B2)

## Escopo

Use este runbook para ocorrencias com o codigo:

- `STORAGE_ERROR`

## Sintomas

- Worker coletou XML do portal mas falhou ao gravar no bucket S3.
- Item marcado com erro de storage, apesar de `chave_nfse` valida.
- Execucao termina `partial` ou `failed` mesmo com portal respondendo.
- Log em `worker_core.storage` mostra `StorageError` apos esgotar retries
  (4 tentativas com backoff 0.5s..8s — CORE-05).

## Severidade

`STORAGE_ERROR` nasce como **`critical`**: impacta compliance (retencao
90d ADR-003) e pode indicar saturacao/queda do provider.

## Causas comuns

1. **Credenciais B2 invalidadas** (`S3_ACCESS_KEY_ID`/
   `S3_SECRET_ACCESS_KEY` revogadas ou rotacionadas sem atualizar `.env`).
2. **Bucket inexistente ou renomeado** (`NoSuchBucket`).
3. **Permissao negada** (`AccessDenied`) — politica do bucket mudou.
4. **Provider fora do ar** (`SlowDown`, `ServiceUnavailable`,
   `InternalError` persistentes).
5. **Quota/billing do Backblaze** — conta suspensa por saldo ou limite.

## Diagnostico

1. Inspecionar `detail` da ocorrencia: codigo do erro S3 (AccessDenied,
   NoSuchBucket, etc.) direciona para a causa.
2. Rodar smoke test com o cliente CLI:
   ```bash
   aws --endpoint-url "$S3_ENDPOINT" s3 ls "s3://$S3_BUCKET/tenants/" \
     --profile nfse-saas
   ```
3. Conferir painel da Backblaze (consumo, chave de API, bucket lifecycle).
4. Checar outras ocorrencias `STORAGE_ERROR` recentes — mesma causa
   geralmente atinge varios tenants simultaneamente.

## Mitigacao

### Credenciais invalidas

1. Gerar nova Application Key em Backblaze com escopo por bucket.
2. Atualizar `S3_ACCESS_KEY_ID` e `S3_SECRET_ACCESS_KEY` no `.env` da VPS.
3. Reiniciar `apps/worker` + `apps/api` para recarregar envs.
4. Reprocessar execucoes afetadas (ver runbook de `REPROCESS_NEEDED`).

### Provider fora / 5xx persistentes

1. Pausar agendamentos pesados para nao enfileirar upload que vai
   falhar de novo.
2. Esperar status page do Backblaze normalizar (ou aplicar Cloudflare R2
   como fallback se configurado — nao padrao).
3. Apos recuperacao, reprocessar execucoes com `partial`.

### Bucket errado / policy

1. Confirmar valor de `S3_BUCKET` no `.env` corresponde ao provisionado
   em INFRA-06.
2. Revalidar politica do bucket (permitir PUT/GET da chave de API).
3. Se houver mudanca intencional de layout, nao executar reprocessamento
   sem primeiro alinhar com engenharia — objetos podem ficar orfaos.

## Quando escalar

- Taxa de `STORAGE_ERROR` > 1% por mais de 10 minutos: abrir incidente
  publico na status page (quando disponivel).
- Qualquer erro que sugira perda de dados (`sha256` divergente entre o
  que o worker calculou e o que o bucket retornou apos o upload).

## Prevencao

- Alerta Grafana em `storage.upload.fail_total` (INFRA-07).
- Backup diario do Postgres em bucket irmao (`tenants-exports/`) com
  lifecycle de 30d (INFRA-08).
- Rodizio de chaves de API com lembrete anual — documentar em `docs/ops/`.
