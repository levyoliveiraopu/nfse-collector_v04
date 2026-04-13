# DATA-03 — Schema: executions + execution_items

- **Trilha:** data
- **Tamanho:** M
- **Status:** blocked (aguarda DATA-02)
- **Depende de:** DATA-02

## Objetivo

Tabelas para rastrear cada execucao de coleta e os itens processados.

## Entregaveis

- Migration `0004_executions.py`:
  - `executions` (id, tenant_id, company_id, trigger,
    triggered_by_user_id, period_start, period_end, status,
    started_at, finished_at, nsu_from, nsu_to, items_total,
    items_ok, items_fail, error_summary, timestamps).
  - Indice composto `(tenant_id, company_id, started_at DESC)`.
- Migration `0005_execution_items.py`:
  - `execution_items` (id, execution_id, tenant_id, nsu, chave_nfse,
    cnpj_emitente, data_emissao, valor, xml_object_key, status,
    error_code, error_message, timestamps).
  - Indice `(execution_id)`, `(tenant_id, data_emissao)`.
  - Unico parcial `(tenant_id, chave_nfse) WHERE chave_nfse IS NOT NULL`.
- RLS em ambas.

## Definition of Done

- [ ] Migrations sobem/descem.
- [ ] EXPLAIN verde em query de listagem por periodo.
