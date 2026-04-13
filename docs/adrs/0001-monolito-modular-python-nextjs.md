# ADR-001 — Monolito modular Python (FastAPI) + Next.js

- **Status:** Aceito
- **Data:** 2026-04-13
- **Decisores:** @LevyOliveirabr

## Contexto

Produto SaaS multi-tenant operado por solo founder, com backend tecnico
legado em Python (coleta ADN + geracao de XML/Excel). Precisamos de:

- Reuso do motor existente (`src/`).
- Baixo custo operacional (1 VPS no inicio).
- Evolucao rapida sem over-engineering.

## Alternativas consideradas

1. **Microservicos desde o inicio** — Rejeitado: custo operacional e
   complexidade incompativeis com solo founder.
2. **Monolito unico Django + templates** — Rejeitado: UX/UI alvo exige SPA
   moderna; Django templates limitam o frontend profissional.
3. **Node.js full-stack (Nest + Next)** — Rejeitado: descarta reuso do motor
   Python existente (ADN/mTLS/NSU).
4. **Monolito modular Python (FastAPI) + Next.js separado** — **Aceito.**

## Decisao

- Backend: **FastAPI** + SQLAlchemy + Alembic, organizado em modulos
  (`tenants`, `companies`, `credentials`, `executions`, `occurrences`,
  `files`, `schedules`, `billing`, `auth`).
- Worker: processo Python separado (`apps/worker`) consumindo Redis (RQ),
  usando `packages/worker-core`.
- Frontend: **Next.js 14 (App Router)** em TypeScript, dois apps separados
  (`web-app` para painel logado, `web-site` para landing).
- Contrato entre front e back: OpenAPI gerado pelo FastAPI; cliente TS
  gerado automaticamente.

## Consequencias

**Positivas**
- Reuso integral do motor ADN em Python.
- Separacao clara entre site publico e painel (deploys independentes).
- Baixo custo: tudo roda em 1 VPS.

**Negativas**
- Dois runtimes (Python + Node) para operar.
- Gerar cliente TS a partir do OpenAPI adiciona uma etapa de build.

## Reavaliacao

Reavaliar quando: MRR > 10x custo atual **ou** necessidade de escalar algum
dominio de forma independente (ex: worker-core em alto volume).
