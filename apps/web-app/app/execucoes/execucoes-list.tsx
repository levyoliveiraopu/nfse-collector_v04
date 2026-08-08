"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { StatusBadge } from "@/components/ui/status-badge";
import { useAuth } from "@/components/auth/auth-provider";
import {
  EXECUTION_STATUS_LABEL,
  ExecutionsApiError,
  decideExecutionBadge,
  listExecutions,
  type Execution,
  type ExecutionStatus,
} from "@/lib/api/executions";

const STATUS_FILTER_OPTIONS: { value: "" | ExecutionStatus; label: string }[] = [
  { value: "", label: "Todos os status" },
  { value: "queued", label: "Na fila" },
  { value: "running", label: "Em execucao" },
  { value: "succeeded", label: "Concluida" },
  { value: "partial", label: "Parcial" },
  { value: "failed", label: "Falhou" },
  { value: "cancelled", label: "Cancelada" },
];

const PAGE_SIZE = 20;

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatRange(from: string, to: string): string {
  try {
    const f = new Date(from + "T12:00:00Z");
    const t = new Date(to + "T12:00:00Z");
    const fmt = new Intl.DateTimeFormat("pt-BR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      timeZone: "UTC",
    });
    return `${fmt.format(f)} – ${fmt.format(t)}`;
  } catch {
    return `${from} – ${to}`;
  }
}

export function ExecucoesList() {
  const { accessToken, refresh } = useAuth();
  const [status, setStatus] = React.useState<"" | ExecutionStatus>("");
  const [page, setPage] = React.useState(1);

  // Reset para pagina 1 ao mudar filtro.
  React.useEffect(() => {
    setPage(1);
  }, [status]);

  const query = useQuery({
    queryKey: ["executions:list", { status, page }],
    queryFn: async () => {
      return listExecutions(
        {
          page,
          pageSize: PAGE_SIZE,
          status: status === "" ? undefined : status,
        },
        {
          accessToken,
          onTokenRefreshed: () => {
            void refresh();
          },
        },
      );
    },
    enabled: Boolean(accessToken),
  });

  const items: Execution[] = query.data?.items ?? [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section
      aria-label="Execucoes"
      data-help-id="executions-primary"
      className="rounded-lg border border-border bg-card text-card-foreground shadow-sm"
    >
      <header className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-3">
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Status</span>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as "" | ExecutionStatus)}
            className="h-8 rounded-md border border-input bg-background px-2 text-sm"
            aria-label="Filtrar por status"
          >
            {STATUS_FILTER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <span className="ml-auto text-xs text-muted-foreground" data-testid="total-count">
          {total} execucao{total === 1 ? "" : "es"}
        </span>
      </header>

      {query.isLoading ? (
        <p className="px-4 py-6 text-sm text-muted-foreground" role="status">
          Carregando execucoes…
        </p>
      ) : query.isError ? (
        <div className="flex flex-col gap-2 px-4 py-6 text-sm" role="alert">
          <p className="text-destructive">
            {query.error instanceof ExecutionsApiError
              ? query.error.message
              : "Nao foi possivel carregar as execucoes."}
          </p>
          <button
            type="button"
            onClick={() => query.refetch()}
            className="self-start rounded-md border border-border px-3 py-1 text-xs hover:bg-accent"
          >
            Tentar novamente
          </button>
        </div>
      ) : items.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted-foreground">
          Nenhuma execucao registrada ainda. Clique em &quot;Nova execucao&quot; para comecar.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2 text-left">Status</th>
                <th className="px-4 py-2 text-left">Empresa</th>
                <th className="px-4 py-2 text-left">Periodo</th>
                <th className="px-4 py-2 text-right">Items</th>
                <th className="px-4 py-2 text-left">Iniciada</th>
                <th className="px-4 py-2" aria-label="Acoes" />
              </tr>
            </thead>
            <tbody>
              {items.map((exec) => (
                <tr key={exec.id} className="border-t border-border hover:bg-muted/30">
                  <td className="px-4 py-2">
                    <StatusBadge
                      variant={decideExecutionBadge(exec.status)}
                      label={EXECUTION_STATUS_LABEL[exec.status]}
                      size="sm"
                    />
                  </td>
                  <td className="px-4 py-2 font-mono text-xs" title={exec.company_id}>
                    {exec.company_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-2 text-xs">
                    {formatRange(exec.period_start, exec.period_end)}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {exec.items_ok + exec.items_fail} / {exec.items_total}
                  </td>
                  <td className="px-4 py-2 text-xs">{formatDate(exec.started_at)}</td>
                  <td className="px-4 py-2 text-right">
                    <Link
                      href={`/execucoes/${exec.id}`}
                      className="text-primary hover:underline"
                    >
                      Abrir
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 ? (
        <footer className="flex items-center justify-between border-t border-border px-4 py-2 text-xs">
          <span>
            Pagina {page} de {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="rounded-md border border-border px-2 py-1 disabled:opacity-50"
            >
              Anterior
            </button>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-md border border-border px-2 py-1 disabled:opacity-50"
            >
              Proxima
            </button>
          </div>
        </footer>
      ) : null}
    </section>
  );
}
