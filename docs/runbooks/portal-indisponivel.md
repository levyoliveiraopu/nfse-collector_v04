# Runbook — Portal indisponível / rate-limit

Este runbook cobre incidentes de integração com portais de prefeituras para os eventos:

- `PORTAL_5XX`
- `PORTAL_TIMEOUT`
- `RATE_LIMIT`

## 1) Triagem rápida (5 minutos)

1. Identificar tenant impactado e endpoint do portal alvo.
2. Validar se houve deploy recente no SaaS (API/worker/rede) nos últimos 30 minutos.
3. Conferir métricas/logs dos workers:
   - taxa de erro por prefeitura;
   - latência p95/p99;
   - fila RQ (crescimento anormal).
4. Reproduzir chamada mínima de health-check no portal externo.

## 2) Como diferenciar falha nossa x falha do portal

### Sinais de falha do portal (externa)

- Erros `5xx` concentrados em **uma prefeitura** e em múltiplos tenants.
- Timeouts aumentam sem aumento de CPU/memória dos workers.
- Chamadas diretas ao endpoint público do portal também falham.
- Sem deploy recente correlacionado no nosso lado.

### Sinais de falha nossa (interna)

- Erros em múltiplas prefeituras ao mesmo tempo após deploy.
- Exceções internas nos logs (auth, serialização, mTLS, DNS, pool de conexões).
- Saturação de fila RQ, CPU/memória ou conexões de banco.
- Requisições manuais ao portal funcionam fora do SaaS.

## 3) Estratégia de backoff

Para `PORTAL_5XX` e `PORTAL_TIMEOUT`:

- Tentar novamente com backoff exponencial + jitter.
- Sequência sugerida: `15s`, `45s`, `120s`, `300s`, `600s`.
- Limite de tentativas: 5 por lote/NSU.
- Respeitar idempotência para evitar duplicidade de coleta.

Para `RATE_LIMIT`:

- Se houver `Retry-After`, obedecer prioritariamente.
- Sem `Retry-After`, aplicar janela conservadora de 60s e dobrar até 10 min.
- Reduzir concorrência por prefeitura (throttle por tenant).

## 4) Comunicação com cliente

Avisar cliente quando qualquer condição abaixo ocorrer:

- indisponibilidade contínua > 15 minutos;
- impacto em produção com atraso perceptível na coleta;
- necessidade de ação manual do cliente (ex.: confirmar status no portal local).

Modelo curto de atualização:

> Detectamos instabilidade no portal da prefeitura (erro externo). A coleta segue em
> retentativas automáticas com backoff. Próxima atualização em 30 minutos.

## 5) Quando abrir ticket público (status page)

Abrir incidente público quando:

- 2+ tenants afetados pela mesma prefeitura por mais de 20 minutos; ou
- degradação total da coleta para um portal crítico; ou
- `RATE_LIMIT` persistente com impacto operacional por mais de 30 minutos.

Campos mínimos do ticket público:

- início do incidente (UTC);
- prefeituras/portais afetados;
- sintomas (`5xx`, timeout, rate-limit);
- mitigação aplicada (backoff/throttle);
- próximo horário de atualização.

## 6) Encerramento

1. Confirmar recuperação (taxa de sucesso normalizada).
2. Drenar backlog da fila RQ.
3. Encerrar status page (se aberta) com horário final.
4. Registrar post-mortem curto com causa provável e ação preventiva.
