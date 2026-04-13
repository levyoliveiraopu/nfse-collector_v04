# APP-03 — /empresas lista + detalhe (abas)

- **Trilha:** app
- **Tamanho:** L
- **Status:** blocked (aguarda DS-06 + API-05)
- **Depende de:** DS-06, API-05

## Objetivo

Gerenciar CNPJs do tenant.

## Entregaveis

- `/empresas` lista com DataTable + filtros (status, UF, ultimo sucesso).
- Acao "Nova empresa" (modal com CNPJInput + razao social + municipio).
- `/empresas/[id]` com abas:
  - **Visao geral**: dados + ultima execucao + proxima agendada.
  - **Execucoes** (DataTable filtrada).
  - **Credencial** (status + upload — APP-04).
  - **Agendamentos**.
  - **Arquivos**.
  - **Ocorrencias**.

## Definition of Done

- [ ] CRUD funciona.
- [ ] Abas carregam sob demanda (lazy).
