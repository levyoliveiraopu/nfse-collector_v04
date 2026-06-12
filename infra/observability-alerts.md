# Alertas operacionais — PROD-READY item 4

Este arquivo define o contrato de alerta para o ambiente real. A stack
versionada entrega Loki + Promtail + Grafana + Uptime Kuma; os segredos de
notificacao ficam fora do repo.

## Canais

- Primario: Telegram via Uptime Kuma ou Grafana contact point.
- Segredos: `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` somente no `.env`/UI da VPS.
- Exemplo sem segredo real: `infra/compose/grafana/provisioning/alerting/contact-points.example.yml`.

## Alertas obrigatorios

| Alerta | Sinal | Janela | Severidade | Runbook |
|---|---|---:|---|---|
| Fila parada / worker indisponivel | Uptime Kuma monitor `worker` em `/healthz` falha ou LogQL sem `jobs.run_execution.ok` apesar de `queue.enqueued` | 5 min | alta | `docs/runbooks/fila-travada.md` |
| Scheduler sem tick | LogQL `count_over_time(... "scheduler.tick.done" [5m]) == 0` | 5 min | alta | `docs/runbooks/fila-travada.md` |
| Taxa de erro alta | LogQL de `error|exception|traceback|critical` acima de baseline | 5 min | media/alta | `docs/runbooks/erro-desconhecido.md` |
| Portal indisponivel | ocorrencias/logs `PORTAL_5XX`, `PORTAL_TIMEOUT`, `PORTAL_RATE_LIMIT` | 10 min | media | `docs/runbooks/portal-indisponivel.md` |
| Backup falhou | JSON de `backup-postgres` com `status="failed"` ou ausencia de `status="success"` em 26h | 26 h | critica | `docs/runbooks/backup-falhou.md` |
| SSL expirando | Uptime Kuma Certificate Expiry Notification | 14/7/3 dias | alta | `docs/runbooks/ssl-expirando.md` |

## Queries LogQL de referencia

```logql
# Scheduler sem tick
sum(count_over_time({container_id=~".+"} |~ "scheduler\\.tick\\.done" [5m]))

# Jobs enfileirados
sum(count_over_time({container_id=~".+"} |~ "queue\\.enqueued" [5m]))

# Jobs concluidos
sum(count_over_time({container_id=~".+"} |~ "jobs\\.run_execution\\.ok" [5m]))

# Erros por container
sum by (container_id) (count_over_time({container_id=~".+"} |~ "(?i)(error|exception|traceback|critical)" [5m]))

# Backup falhou
sum(count_over_time({job="varlogs"} |~ "backup-postgres" |~ '"status":"failed"' [26h]))
```

## Evidencia operacional minima antes do go-live

1. Abrir Grafana e confirmar dashboard `NFS-e — Logs API & Worker`.
2. Criar/validar monitores Uptime Kuma para `site`, `app`, `api`, `worker`, `ops` e certificado TLS.
3. Disparar teste controlado de notificacao Telegram no Uptime Kuma.
4. Executar um backup manual e confirmar log `backup-postgres` com `status="success"`.
5. Simular ao menos um incidente usando `docs/runbooks/incident-simulation-checklist.md`.
