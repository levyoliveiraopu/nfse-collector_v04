# Runbook — erro desconhecido

## Escopo

Use este runbook para ocorrencias com o codigo:

- `UNKNOWN`

`UNKNOWN` e o **ultimo recurso** de classificacao. Sempre que surgir,
abrir uma issue de engenharia para promover a causa-raiz a um codigo
proprio e atualizar `docs/architecture/occurrence-codes.md`.

## Sintomas

- Falha nao se encaixa em nenhum dos codigos do catalogo.
- Stack trace aponta para lugar inesperado
  (rede, filesystem, dependencia externa).
- Ocorrencia foi criada por um ramo `except Exception` defensivo do
  worker.

## Diagnostico

1. Capturar `detail` completo e, se houver, `traceback` anexado nos logs
   estruturados (`logger.getLogger("worker_core.collector")`).
2. Identificar:
   - tenant + company + execution afetados;
   - janela temporal (isolado vs. lote);
   - se reproduz em outra empresa / outra prefeitura.
3. Procurar o mesmo `detail` em logs anteriores — pode ser conhecido
   sem codigo atribuido ainda.

## Mitigacao

### Se o erro for transiente

1. Acknowledge da ocorrencia.
2. Reprocessar a execucao (runbook `REPROCESS_NEEDED`).
3. Se resolver, marcar como **resolved** com nota detalhada e agendar
   backlog de classificacao.

### Se reproduzir

1. NAO reprocessar cegamente — pode gerar loop de alertas.
2. Pausar agendamentos da empresa afetada
   (`POST /schedules/:id { enabled: false }`).
3. Abrir issue de engenharia com:
   - stack trace / `detail`;
   - passo a passo para reproduzir;
   - hipotese de novo codigo (ex.: `PORTAL_AUTH_CHALLENGE`,
     `CERT_CHAIN_INCOMPLETE`);
4. Quando o novo codigo for emitido, atualizar o runbook e as tabelas
   em `docs/architecture/occurrence-codes.md`.

## Quando escalar

- Mais de 10 `UNKNOWN` em 24h: sinal de regressao em deploy recente.
  Reverter se a janela coincidir com o ultimo release.
- `UNKNOWN` com `severity=critical` (promovido pelo emissor): tratar
  como P1 ate reclassificar.

## Prevencao

- Review regular das ocorrencias `UNKNOWN` em reuniao operacional
  semanal.
- Cada `UNKNOWN` novo deve ser convertido em codigo canonico ou em issue
  explicando por que nao deve virar — zero tolerancia a `UNKNOWN`
  recorrente sem investigacao.
