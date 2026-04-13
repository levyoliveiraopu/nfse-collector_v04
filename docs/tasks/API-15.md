# API-15 — Export ZIP assincrono

- **Trilha:** api
- **Tamanho:** M
- **Status:** blocked (aguarda API-11)
- **Depende de:** API-11

## Objetivo

Permitir cliente pedir ZIP com varios XMLs de uma empresa/periodo; gerar
assincronamente e notificar quando pronto.

## Entregaveis

- `POST /exports` com body `{ company_id, period_start, period_end,
  kind: "zip_xml" | "excel_consolidated" }`.
- Enfileira job `build_export(file_id)`.
- Worker baixa XMLs do S3, zipa em `tmpfs`, faz upload do ZIP e marca
  `files` como pronto + preenche `expires_at = now + 30d`.
- Notificacao (in-app + email) com link pre-assinado.
- Endpoint `GET /exports/{id}` retorna status.

## Definition of Done

- [ ] Export de 500 XMLs completa e download do ZIP abre.
- [ ] Limite de tamanho: aborta export > 2GB com erro claro.
