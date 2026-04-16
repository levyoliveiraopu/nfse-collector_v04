/**
 * Dados de teste para a pagina /assinatura (APP-10).
 *
 * Enquanto o endpoint real de billing/usage nao existe (ADR-004: billing
 * adiado, schema `plans`/`subscriptions` ja criado em DATA-05 mas sem
 * API publica), a pagina consome este mock. Um ticket API futuro troca
 * esta funcao por um fetch real sem tocar no layout da pagina.
 *
 * O formato abaixo espelha o shape esperado do endpoint futuro:
 * - `plan.code` casa com `plans.code` do seed DATA-07 (`starter`/`pro`/`scale`).
 * - `limits` reflete `plans.limits` (jsonb).
 * - `usage` sera calculado em runtime pelo backend (contagens agregadas).
 */
export type SubscriptionMetric = {
  used: number;
  limit: number;
};

export type SubscriptionSnapshot = {
  plan: {
    code: "starter" | "pro" | "scale";
    name: string;
    status: "active" | "suspended" | "canceled";
  };
  usage: {
    companies: SubscriptionMetric;
    executionsMonth: SubscriptionMetric;
    users: SubscriptionMetric;
  };
};

/**
 * Snapshot de teste — tenant `demo` em plano `pro` (alinhado com DATA-07).
 * Valores de `used` escolhidos para ilustrar os tres regimes visuais:
 * folga, alerta (>=80%) e limite atingido (100%).
 */
export const MOCK_SUBSCRIPTION: SubscriptionSnapshot = {
  plan: {
    code: "pro",
    name: "Pro",
    status: "active",
  },
  usage: {
    companies: { used: 3, limit: 10 },
    executionsMonth: { used: 420, limit: 500 },
    users: { used: 5, limit: 5 },
  },
};

export function getSubscriptionSnapshot(): SubscriptionSnapshot {
  return MOCK_SUBSCRIPTION;
}
