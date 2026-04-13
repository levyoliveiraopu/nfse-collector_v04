# ADR-004 — Billing adiado: schema pronto, integracao depois

- **Status:** Aceito
- **Data:** 2026-04-13

## Contexto

Fase atual prioriza implantacao do produto. Venda/pagamento sera
validada apos MVP funcional com piloto remunerado a 50% off (cobranca
manual via PIX/boleto avulso).

## Decisao

- Tabelas `plans` e `subscriptions` fazem parte do schema desde o
  inicio (schema e barato).
- Endpoints publicos de upgrade/downgrade/checkout **nao** sao
  expostos no MVP.
- `/assinatura` no painel exibe apenas plano atribuido + uso vs limite.
- Criacao de tenant e atribuicao de plano: via script CLI / endpoint
  admin interno (`ops.dominio`).
- Gateway (Asaas/Stripe/Iugu) e decidido apos 10 clientes pagantes
  manuais validando disposicao a pagar.

## Consequencias

**Positivas**
- Reduz escopo do MVP.
- Evita lock-in prematuro em gateway.
- Schema pronto permite plug-in rapido quando decidir.

**Negativas**
- Cobranca manual nao escala alem de ~20 clientes.
- Precisara de 2a migration grande quando integracao entrar.

## Reavaliacao

Reavaliar ao atingir 10 clientes pagantes.
