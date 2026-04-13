# ADR-002 — Multi-tenant single-DB com Row Level Security

- **Status:** Aceito
- **Data:** 2026-04-13

## Contexto

SaaS multi-tenant com previsao de 5 a ~300 tenants no medio prazo. Solo
founder precisa minimizar esforco operacional. Isolamento de dados entre
tenants e requisito obrigatorio.

## Alternativas consideradas

1. **Database-per-tenant** — Rejeitado: custo operacional (migrations x N,
   backup x N, monitoring x N) inviavel para solo founder.
2. **Schema-per-tenant** — Rejeitado: migrations complexas, proliferacao
   de schemas, mesmos problemas operacionais.
3. **Single-DB com coluna `tenant_id` + Row Level Security (RLS)** —
   **Aceito.**

## Decisao

- Todas as tabelas de negocio tem coluna `tenant_id UUID NOT NULL`.
- RLS habilitado por padrao em todas as tabelas com `tenant_id`.
- Politica RLS usa GUC (variavel de sessao Postgres) `app.current_tenant`
  setada via `SET LOCAL` por request.
- Middleware da API seta a variavel logo apos autenticar.
- Worker seta a variavel ao processar job.
- Role de aplicacao (`app_user`) **sem** `BYPASSRLS`; role de admin
  (`app_admin`) apenas para migrations.
- Testes automatizados garantem isolamento cross-tenant (DATA-06).

## Consequencias

**Positivas**
- Operacao simples (1 banco, 1 backup).
- Isolamento enforce no banco mesmo em bug de aplicacao.
- Migrations unicas.

**Negativas**
- Dependencia de disciplina em setar `app.current_tenant`.
- Queries precisam ser analisadas para garantir uso de indices com
  `tenant_id` como primeira coluna composta.
- Risco de "tenant gigante" impactar os demais (noisy neighbor) — mitigar
  com indices adequados e, futuramente, particionamento.

## Reavaliacao

Se um tenant passar de ~30% dos dados totais ou houver requisito legal
de isolamento fisico, migrar aquele tenant especifico para schema/db
dedicado.
