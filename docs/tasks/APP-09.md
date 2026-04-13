# APP-09 — /usuarios + convites

- **Trilha:** app
- **Tamanho:** M
- **Status:** blocked (aguarda API-02 + API-04)
- **Depende de:** API-02, API-04

## Objetivo

Gerenciar usuarios do tenant.

## Entregaveis

- Lista com role + ultimo login + status.
- Convidar (email + role) envia email com link.
- Revogar convite pendente.
- Alterar role (owner nao pode ser rebaixado por admin).
- Remover usuario do tenant.

## Definition of Done

- [ ] Convite E2E: envia, aceita, aparece na lista.
- [ ] Restricoes de role testadas.
