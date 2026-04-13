# INFRA-07 — Observabilidade minima (Loki + Grafana + Uptime Kuma)

- **Trilha:** infra
- **Tamanho:** M
- **Status:** ready (apos INFRA-02)
- **Depende de:** INFRA-02

## Objetivo

Ter logs centralizados, dashboards e alertas de uptime.

## Entregaveis

- `infra/compose/docker-compose.obs.yml` com:
  - `grafana` (porta 3001 interna).
  - `loki`.
  - `promtail` coletando logs de `/var/lib/docker/containers`.
  - `uptime-kuma`.
- Nginx expoe `ops.<dominio>/grafana` e `ops.<dominio>/uptime`
  protegido por basic auth + IP allowlist.
- Datasource Loki configurado no Grafana.
- Dashboard inicial com logs de API e worker.
- Uptime Kuma monitorando: site, app, api `/health`, worker `/healthz`.
- Canal de alerta Telegram configurado e testado.

## Definition of Done

- [ ] Grafana acessivel em `ops.<dominio>/grafana` (restrito).
- [ ] Logs de containers aparecem em tempo real.
- [ ] Alerta Telegram dispara em teste manual.
