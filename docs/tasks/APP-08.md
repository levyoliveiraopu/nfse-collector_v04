# APP-08 — /arquivos + download

- **Trilha:** app
- **Tamanho:** M
- **Status:** blocked (aguarda API-11 + API-15)
- **Depende de:** API-11, API-15

## Objetivo

Listar arquivos gerados e permitir download via URL pre-assinada.

## Entregaveis

- Lista filtravel (empresa, periodo, kind: xml/excel/zip).
- Banner permanente lembrando **retencao 90 dias** (ADR-003).
- Botao "Gerar ZIP" (abre modal de seleccao de empresa + periodo)
  que dispara export (API-15).
- Download via URL pre-assinada (API-11).

## Definition of Done

- [ ] Download funciona.
- [ ] Banner de retencao visivel sempre.
