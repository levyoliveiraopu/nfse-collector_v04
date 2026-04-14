# STATE — NFS-e SaaS

> Fonte unica de verdade sobre o estado atual do projeto.
> Toda PR deve atualizar este arquivo antes do merge.

## Decisoes Ativas

| ID | Decisao | Status |
|----|---------|--------|
| ADR-001 | Monolito modular Python (FastAPI) + Next.js | ativo |
| ADR-002 | Multi-tenant single-DB com Row Level Security | ativo |
| ADR-003 | Storage S3 externo, cifra PFX AES-GCM, retencao 90d sem arquivamento | ativo |
| ADR-004 | Billing adiado: schema pronto, integracao depois | ativo |
| ADR-005 | Deploy Docker Compose em VPS Hostinger + Nginx host | ativo |

## Em Andamento

_Nenhuma tarefa ativa._

## Concluidos

- **CORE-01** — Motor ADN legado extraido de `src/` para pacote Python
  instalavel em `packages/worker-core/`; `src/` vira shim retro-compativel
  (PR #80).
- **INFRA-06** — Bucket S3 (Backblaze B2): template de lifecycle,
  `.env.example`, runbook manual e smoke test prontos; aplicacao no
  console/CLI da Backblaze e geracao da Application Key ficam a cargo
  do owner (ver `infra/s3-bucket.md` secao 2).

- **DOCS-01** — Termos de Uso criado em `docs/legal/terms.md`, incluindo
  clausula de retencao de 90 dias (ADR-003), pagamento/renovacao/cancelamento,
  limitacao de responsabilidade, foro/legislacao e orientacao de referencia
  para signup e rota `/legal` do app/site.

## Proximas Destravadas (prontas para iniciar)

- **INFRA-01** — Hardening inicial da VPS Hostinger
- **DOCS-02** — Politica de Privacidade + LGPD
- **DATA-01** — Schema inicial: tenants, users, tenant_users (depende de `apps/api` inicializado; ver API-01)

> Nota: CORE-05, API-06, API-11 e INFRA-08 dependem de INFRA-06 **e**
> de outros tickets (CORE-01 / API-05 / DATA-05 / INFRA-05), portanto
> continuam bloqueados ate que essas dependencias sejam concluidas.

## Bloqueadas

- **SITE-00..10** — aguardando definicao do nome comercial.
- **API-01** — aguardando `GOV-01` (feito) e decisao sobre estrutura de pacote Python.

## Limite de WIP

Maximo **4 tarefas** em "Em Andamento" simultaneamente.

## Pendencias de Decisao

| Item | Prazo sugerido | Bloqueia |
|------|----------------|----------|
| Nome comercial / dominio definitivo | antes da Fase 7 | Trilha SITE inteira |
| Gateway de pagamento (Asaas/Stripe/Iugu) | antes do primeiro cliente pago | API de billing |

## Ultima atualizacao

- Data: 2026-04-13
- PR: #81 — DOCS-01 (Termos de Uso com clausula de retencao 90 dias)
- Autor: @codex
- Nota: workflow `pr-guardrail` exige STATE.md + CHANGELOG.md + `Closes #N` em todo PR para main.

## Links Rapidos

- Backlog completo: `docs/tasks/`
- Como usar os tickets: `docs/tasks/README.md`
- ADRs: `docs/adrs/`
- Contribuicao: `CONTRIBUTING.md`
