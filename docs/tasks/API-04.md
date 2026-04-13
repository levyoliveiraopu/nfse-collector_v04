# API-04 — RBAC (owner, admin, operator, viewer)

- **Trilha:** api
- **Tamanho:** M
- **Status:** blocked (aguarda API-03)
- **Depende de:** API-03

## Objetivo

Controle de permissoes por role.

## Entregaveis

- Decorator/dependency `require_role("admin")` (e combinacoes).
- Matriz de permissoes documentada em
  `docs/architecture/rbac-matrix.md`.
- Roles seedadas em `tenant_users`.
- 403 claro quando falta permissao.

## Definition of Done

- [ ] `viewer` recebe 403 ao tentar criar empresa.
- [ ] `owner` nao pode ser removido por admin.
- [ ] Matriz + testes.
