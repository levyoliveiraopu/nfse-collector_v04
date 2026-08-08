import { Building2, CreditCard, Mail, MessageCircle, Play, Users } from "lucide-react";

import { StatusBadge } from "@/components/ui/status-badge";
import { UsageMeter } from "@/components/subscription/usage-meter";
import { getSubscriptionSnapshot } from "@/lib/subscription/mock";

/**
 * Contatos de suporte — placeholders ate SITE-* destravar (nome comercial).
 * Links intencionalmente apontam para dominios/numeros de exemplo.
 */
const SUPPORT_WHATSAPP_URL = "https://wa.me/5500000000000";
const SUPPORT_EMAIL = "suporte@exemplo.local";

export default function AssinaturaPage() {
  const snapshot = getSubscriptionSnapshot();
  const { plan, usage } = snapshot;

  const planBadgeVariant =
    plan.status === "active"
      ? "success"
      : plan.status === "suspended"
        ? "warning"
        : "failed";
  const planBadgeLabel =
    plan.status === "active"
      ? "Ativo"
      : plan.status === "suspended"
        ? "Suspenso"
        : "Cancelado";

  return (
    <div className="flex flex-col gap-6" data-help-id="subscription-primary">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Assinatura</h1>
          <p className="text-sm text-muted-foreground">
            Plano atribuido ao tenant e uso atual em relacao aos limites.
          </p>
        </div>
      </div>

      <section
        aria-label="Plano atual"
        className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5 text-card-foreground shadow-sm sm:flex-row sm:items-center sm:justify-between"
      >
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10 text-primary"
          >
            <CreditCard className="h-5 w-5" />
          </span>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Plano atual
            </p>
            <p className="text-lg font-semibold tracking-tight">{plan.name}</p>
          </div>
        </div>
        <StatusBadge variant={planBadgeVariant} label={planBadgeLabel} />
      </section>

      <section
        aria-label="Uso atual vs limite"
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"
      >
        <UsageMeter
          title="CNPJs cadastrados"
          metric={usage.companies}
          icon={Building2}
        />
        <UsageMeter
          title="Execucoes no mes"
          metric={usage.executionsMonth}
          icon={Play}
        />
        <UsageMeter title="Usuarios" metric={usage.users} icon={Users} />
      </section>

      <section
        aria-label="Alterar plano"
        className="rounded-lg border border-border bg-muted/40 p-5 text-sm"
      >
        <p className="font-medium text-foreground">
          Para alterar plano, entre em contato com o suporte.
        </p>
        <p className="mt-1 text-muted-foreground">
          A cobranca e feita manualmente enquanto a integracao com gateway de
          pagamento nao e concluida.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <a
            href={SUPPORT_WHATSAPP_URL}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <MessageCircle className="h-4 w-4" aria-hidden="true" />
            WhatsApp
          </a>
          <a
            href={`mailto:${SUPPORT_EMAIL}`}
            className="inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Mail className="h-4 w-4" aria-hidden="true" />
            {SUPPORT_EMAIL}
          </a>
        </div>
      </section>

      <section
        aria-label="Historico de faturas"
        className="rounded-lg border border-border bg-card text-card-foreground shadow-sm"
      >
        <header className="border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold">Historico de faturas</h2>
          <p className="text-xs text-muted-foreground">
            Quando a cobranca automatica for ativada, as faturas aparecerao
            aqui.
          </p>
        </header>
        <div className="flex items-center justify-center px-4 py-12 text-sm text-muted-foreground">
          Nenhuma fatura registrada ate o momento.
        </div>
      </section>
    </div>
  );
}
