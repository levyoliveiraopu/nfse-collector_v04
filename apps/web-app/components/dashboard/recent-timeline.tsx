"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  MinusCircle,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";

import {
  EXECUTION_STATUS_LABEL,
  listExecutions,
  periodDateToUtcIso,
  type Execution,
  type ExecutionStatus,
} from "@/lib/api/executions";
import type { PeriodRange } from "@/lib/date/period";

interface RecentTimelineProps {
  period: PeriodRange;
  limit?: number;
}

/**
 * Timeline provisoria das ultimas execucoes. O componente canonico
 * `<Timeline>` chega com DS-08 (bloqueado); aqui mantemos uma lista
 * vertical enxuta para cumprir o DoD do APP-02 sem expor API publica
 * reutilizavel — sera substituida quando DS-08 pousar.
 */
const STATUS_DOT: Record<ExecutionStatus, { Icon: LucideIcon; className: string }> = {
  succeeded: { Icon: CheckCircle2, className: "text-success" },
  partial: { Icon: AlertTriangle, className: "text-warning" },
  failed: { Icon: XCircle, className: "text-destructive" },
  running: { Icon: Loader2, className: "text-primary animate-spin" },
  queued: { Icon: Clock, className: "text-muted-foreground" },
  cancelled: { Icon: MinusCircle, className: "text-muted-foreground" },
};

function formatDateTime(iso: string | null): string {
  if (!iso) return "\u2014";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function executionSummary(exec: Execution): string {
  const total = exec.items_total ?? 0;
  if (total === 0) return "sem items";
  const ok = exec.items_ok ?? 0;
  return `${ok}/${total} OK`;
}

export function RecentTimeline({ period, limit = 10 }: RecentTimelineProps) {
  const { accessToken, refresh } = useAuth();

  const query = useQuery({
    queryKey: ["dashboard:timeline", period.from, period.to, limit],
    queryFn: ({ signal }) =>
      listExecutions(
        {
          from: periodDateToUtcIso(period.from, "start"),
          to: periodDateToUtcIso(period.to, "endExclusive"),
          page: 1,
          page_size: limit,
        },
        {
          accessToken,
          onTokenRefreshed: () => {
            void refresh();
          },
          signal,
        },
      ),
    enabled: Boolean(accessToken),
  });

  return (
    <section
      aria-label="Ultimas execucoes"
      className="rounded-lg border border-border bg-card text-card-foreground shadow-sm"
    >
      <header className="flex items-baseline justify-between gap-3 border-b border-border px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold">Ultimas execucoes</h2>
          <p className="text-xs text-muted-foreground">
            As {limit} execucoes mais recentes no periodo selecionado.
          </p>
        </div>
      </header>

      {query.isPending ? (
        <div className="px-4 py-6" role="status" aria-busy="true">
          <ul className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <li
                key={i}
                aria-hidden="true"
                className="h-10 animate-pulse rounded-md bg-muted"
              />
            ))}
          </ul>
          <span className="sr-only">Carregando execucoes...</span>
        </div>
      ) : query.isError ? (
        <div className="flex items-center gap-2 px-4 py-6 text-sm text-destructive">
          <AlertTriangle aria-hidden="true" className="h-4 w-4" />
          <span>Falha ao carregar execucoes recentes.</span>
        </div>
      ) : query.data && query.data.items.length > 0 ? (
        <ol className="divide-y divide-border" data-testid="recent-timeline">
          {query.data.items.map((exec) => {
            const { Icon, className } = STATUS_DOT[exec.status];
            return (
              <li key={exec.id} className="flex items-center gap-3 px-4 py-3">
                <Icon
                  aria-hidden="true"
                  className={`h-4 w-4 shrink-0 ${className}`}
                />
                <div className="min-w-0 flex-1">
                  <Link
                    href={`/execucoes/${exec.id}`}
                    className="block truncate text-sm font-medium text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {EXECUTION_STATUS_LABEL[exec.status]} — {executionSummary(exec)}
                  </Link>
                  <p className="truncate text-xs text-muted-foreground tabular-nums">
                    {formatDateTime(exec.started_at ?? exec.created_at)}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      ) : (
        <div className="flex items-center justify-center px-4 py-10 text-sm text-muted-foreground">
          Nenhuma execucao registrada no periodo.
        </div>
      )}
    </section>
  );
}
