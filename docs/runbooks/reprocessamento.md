# Runbook — reprocessamento necessario

## Escopo

Use este runbook para ocorrencias com o codigo:

- `REPROCESS_NEEDED`

## Sintomas

- Item de coleta ficou em estado intermediario apos falha transiente
  (rede, portal, storage) e precisa ser coletado de novo.
- Execucao anterior terminou com status `partial` ou `failed` e alguns
  `chave_nfse` nao foram gravados.
- Ocorrencia foi criada com severity `info` para sinalizar que um retry
  manual e suficiente.

## Causas comuns

1. Falha transiente do portal da prefeitura (ver `PORTAL_5XX`/
   `PORTAL_TIMEOUT`) ja resolvida.
2. Throttling anterior (`RATE_LIMIT`) que liberou apos janela de espera.
3. Erro de storage S3 pontual (ver `STORAGE_ERROR`) ja estabilizado.
4. Operador identificou item faltante apos reconciliacao manual.

## Diagnostico

1. Abrir a ocorrencia no inbox e anotar `company_id` + `execution_id`
   (quando existir) + `detail`.
2. Confirmar que a causa raiz (portal/storage/rate-limit) ja foi mitigada
   — nao reprocessar enquanto a dependencia estiver instavel.
3. Verificar `last_nsu` da empresa: reprocessar a partir do NSU informado
   no `detail` ou usar modo incremental.

## Mitigacao

1. No detalhe da ocorrencia, usar a acao **"Reprocessar"** — abre
   `/execucoes/nova` pre-preenchido com a empresa e a janela sugerida
   (APP-05).
2. Acompanhar a nova execucao ate `succeeded`.
3. Se os itens que faltavam foram gravados com `ON CONFLICT DO NOTHING`
   (idempotencia de API-13), a execucao e segura mesmo que dispare em
   cima de NSUs ja coletados.
4. Marcar a ocorrencia como **resolved** com nota explicando:
   - causa-raiz original (codigo + link do PR/incidente);
   - `execution_id` do reprocessamento;
   - resultado (quantos itens recuperados).

## Quando escalar

- Reprocessamento falha 2x seguidas com o mesmo erro: abrir ocorrencia de
  nivel superior (`PORTAL_5XX` persistente ou `STORAGE_ERROR`) e seguir
  os runbooks correspondentes.
- Divergencia de `chave_nfse` entre portal e banco: nao reprocessar —
  abrir investigacao manual com o time de engenharia.

## Prevencao

- Alertas do Uptime Kuma (INFRA-07) pegam a causa-raiz antes do
  reprocessamento virar rotina.
- Metricas de `execution.status=partial` por prefeitura apontam portais
  instaveis que justificam reduzir concorrencia ou aumentar backoff.
