# Billing, planos e limites

Este documento organiza o item 5.3 do checklist de producao.

## Estado atual versionado

- Existem tabelas `plans` e `subscriptions` na migration `0014_plans_subscriptions`.
- `companies` ja consulta `plans.limits->>'max_companies'` para limitar empresas por tenant.
- A tela `dashboard/assinatura` ainda usa mock no frontend.
- Nome comercial, gateway de pagamento e precificacao final ainda nao estao definidos.

## Limites que devem existir por plano

| Limite | Chave sugerida em `plans.limits` | Aplicacao |
|---|---|---|
| Empresas ativas | `max_companies` | `POST /companies` |
| Usuarios/membros | `max_users` | `POST /tenant/invitations` e aceite |
| Execucoes mensais | `max_executions_monthly` | `POST /executions`, scheduler e reprocess |
| Armazenamento | `max_storage_bytes` | upload XML/export e relatorio de uso |
| Exportacoes mensais | `max_exports_monthly` | `POST /exports` |
| Agendamentos ativos | `max_schedules` | `POST /schedules` |

## Comportamento ao exceder limite

- API deve retornar `403` ou `409` com codigo funcional estavel, exemplo:
  `plan_limit_exceeded` e campo `limit`/`current` quando seguro.
- UI deve exibir CTA para upgrade/contato comercial.
- Scheduler deve pular criacao de novas execucoes quando limite mensal acabar e registrar occurrence/notificacao.
- Reprocessamento manual deve ter regra explicita: contar ou nao contar no limite mensal.

## Preparacao para gateway futuro

- Manter `gateway`, `gateway_customer_id` e `gateway_subscription_id` em `subscriptions` sem acoplar a fornecedor.
- Criar camada `billing/provider.py` quando gateway for escolhido.
- Webhooks devem ser idempotentes por `event_id` e atualizarem `subscriptions.status`.
- Bloqueio por inadimplencia deve usar `tenants.status`/`subscriptions.status` de forma auditavel.

## Decisoes pendentes

- Nome comercial do produto.
- Gateway de pagamento.
- Precos e quotas finais.
- Politica de trial e grace period para `past_due`.
