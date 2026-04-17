"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCcw } from "lucide-react";

import { StatusBadge } from "@/components/ui/status-badge";
import { useAuth } from "@/components/auth/auth-provider";
import {
  EXECUTION_ITEM_STATUS_LABEL,
  EXECUTION_STATUS_LABEL,
  ExecutionsApiError,
  computeProgress,
  decideExecutionBadge,
  getExecution,
  isTerminalStatus,
  listExecutionItems,
  type Execution,
  type ExecutionItem,
  type ExecutionItemStatus,
} from "@/lib/api/executions";

const ITEMS_PAGE_SIZE = 50;

const ITEM_STATUS_FILTERS: {
  value: "" | ExecutionItemStatus;
  label: string;
}[] = [
  { value: "", label: "Todos" },
  { value: "ok", label: "OK" },
  { value: "failed", label: "Falhou" },
  { value: "skipped", label: "Ignorados" },
  { value: "pending", label: "Pendentes" },
];

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatPeriod(from: string, to: string): string {
  try {
    const fmt = new Intl.DateTimeFormat("pt-BR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      timeZone: "UTC",
    });
    return `${fmt.format(new Date(from + "T12:00:00Z"))} – ${fmt.format(
      new Date(to + "T12:00:00Z"),
    )}`;
  } catch {
    return `${from} – ${to}`;
  }
}

function formatValor(valor: string | null): string {
  if (!valor) return "—";
  const n = Number(valor);
  if (Number.isNaN(n)) return valor;
  return n.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

export function ExecucaoDetailView({
  executionId,
}: {
  executionId: string;
}) {
  const { accessToken, refresh } = useAuth();
  const [itemStatusFilter, setItemStatusFilter] = React.useState<
    "" | ExecutionItemStatus
  >("");
  const [itemsPage, setItemsPage] = React.useState(1);
  const [selectedItemIds, setSelectedItemIds] = React.useState<Set<string>>(
    new Set(),
  );

  React.useEffect(() => {
    setItemsPage(1);
    setSelectedItemIds(new Set());
  }, [itemStatusFilter]);

  const ctx = React.useMemo(
    () => ({
      accessToken,
      onTokenRefreshed: () => {
        void refresh();
      },
    }),
    [accessToken, refresh],
  );

  const detail = useQuery({
    queryKey: ["execution:detail", executionId],
    queryFn: () => getExecution(executionId, ctx),
    enabled: Boolean(accessToken),
    refetchInterval: (query) => {
      const data = query.state.data as Execution | undefined;
      if (!data) return 2000;
      return isTerminalStatus(data.status) ? false : 2000;
    },
  });

  const execution = detail.data;
  const terminal = execution ? isTerminalStatus(execution.status) : false;

  const items = useQuery({
    queryKey: [
      "execution:items",
      executionId,
      { status: itemStatusFilter, page: itemsPage },
    ],
    queryFn: () =>
      listExecutionItems(
        executionId,
        {
          page: itemsPage,
          pageSize: ITEMS_PAGE_SIZE,
          status: itemStatusFilter === "" ? undefined : itemStatusFilter,
        },
        ctx,
      ),
    enabled: Boolean(accessToken && execution),
    refetchInterval: terminal ? false : 2000,
  });

  if (detail.isLoading) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        Carregando execucao…
      </p>
    );
  }
  if (detail.isError) {
    const err = detail.error;
    return (
      <div
        role="alert"
        className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
      >
        {err instanceof ExecutionsApiError && err.code === "not_found"
          ? "Execucao nao encontrada ou voce nao tem acesso."
          : "Nao foi possivel carregar esta execucao."}
      </div>
    );
  }
  if (!execution) return null;

  const progress = computeProgress(execution);
  const itemRows: ExecutionItem[] = items.data?.items ?? [];
  const itemsTotal = items.data?.total ?? 0;
  const itemsTotalPages = Math.max(1, Math.ceil(itemsTotal / ITEMS_PAGE_SIZE));

  const toggleItem = (id: string) => {
    setSelectedItemIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const toggleAllVisible = () => {
    setSelectedItemIds((prev) => {
      const allVisibleSelected = itemRows.every((r) => prev.has(r.id));
      if (allVisibleSelected) {
        const next = new Set(prev);
        for (const r of itemRows) next.delete(r.id);
        return next;
      }
      const next = new Set(prev);
      for (const r of itemRows) next.add(r.id);
      return next;
    });
  };

  const reprocessDisabled = true;
  const reprocessTooltip =
    "Reprocessamento sera liberado junto com APP-06 / API-10.";

  return (
    <div className="flex flex-col gap-6">
      <header
        className="rounded-lg border border-border bg-card p-4 shadow-sm"
        data-execution-status={execution.status}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <StatusBadge
              variant={decideExecutionBadge(execution.status)}
              label={EXECUTION_STATUS_LABEL[execution.status]}
            />
            <div>
              <h1 className="text-lg font-semibold">
                Execucao{" "}
                <span className="font-mono text-sm text-muted-foreground">
                  #{execution.id.slice(0, 8)}
                </span>
              </h1>
              <p className="text-xs text-muted-foreground">
                Empresa{" "}
                <span className="font-mono">{execution.company_id.slice(0, 8)}</span>{" "}
                · Periodo {formatPeriod(execution.period_start, execution.period_end)}
              </p>
            </div>
          </div>
          {!terminal ? (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <RefreshCcw className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              Atualizando a cada 2s
            </span>
          ) : null}
        </div>

        <section aria-label="Progresso" className="mt-4 flex flex-col gap-2">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              {progress.processed} de {progress.total} items processados
            </span>
            <span>{progress.percent}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              role="progressbar"
              aria-valuenow={progress.processed}
              aria-valuemin={0}
              aria-valuemax={Math.max(progress.total, 1)}
              aria-label="Progresso da execucao"
              className="h-full bg-primary transition-all"
              style={{ width: `${progress.percent}%` }}
            />
          </div>
          <dl className="mt-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <div>
              <dt className="text-muted-foreground">Total</dt>
              <dd className="font-medium tabular-nums">{execution.items_total}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">OK</dt>
              <dd className="font-medium tabular-nums">{execution.items_ok}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Falhas</dt>
              <dd className="font-medium tabular-nums">{execution.items_fail}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Iniciada</dt>
              <dd className="font-medium">{formatDateTime(execution.started_at)}</dd>
            </div>
          </dl>
          {execution.error_summary ? (
            <p className="mt-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              {execution.error_summary}
            </p>
          ) : null}
        </section>
      </header>

      <section
        aria-label="Items processados"
        className="rounded-lg border border-border bg-card shadow-sm"
      >
        <header className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-3">
          <div
            role="tablist"
            aria-label="Filtrar items por status"
            className="flex flex-wrap gap-1"
          >
            {ITEM_STATUS_FILTERS.map((opt) => {
              const active = itemStatusFilter === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => setItemStatusFilter(opt.value)}
                  className={
                    "rounded-md border px-3 py-1 text-xs transition " +
                    (active
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-input bg-background hover:bg-accent")
                  }
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
          <span className="ml-auto text-xs text-muted-foreground">
            {itemsTotal} item{itemsTotal === 1 ? "" : "s"}
          </span>
          <button
            type="button"
            disabled={reprocessDisabled || selectedItemIds.size === 0}
            title={reprocessTooltip}
            aria-disabled={true}
            className="rounded-md border border-border px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-50"
          >
            Reprocessar selecionados ({selectedItemIds.size})
          </button>
        </header>

        {items.isLoading && itemRows.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted-foreground" role="status">
            Carregando items…
          </p>
        ) : items.isError ? (
          <p className="px-4 py-6 text-sm text-destructive" role="alert">
            Falha ao carregar items.
          </p>
        ) : itemRows.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted-foreground">
            Nenhum item para este filtro.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="w-8 px-3 py-2">
                    <input
                      type="checkbox"
                      aria-label="Selecionar todos visiveis"
                      onChange={toggleAllVisible}
                      checked={
                        itemRows.length > 0 &&
                        itemRows.every((r) => selectedItemIds.has(r.id))
                      }
                    />
                  </th>
                  <th className="px-3 py-2 text-left">Status</th>
                  <th className="px-3 py-2 text-right">NSU</th>
                  <th className="px-3 py-2 text-left">Chave NFS-e</th>
                  <th className="px-3 py-2 text-left">Emitente</th>
                  <th className="px-3 py-2 text-right">Valor</th>
                  <th className="px-3 py-2 text-left">Erro</th>
                </tr>
              </thead>
              <tbody>
                {itemRows.map((item) => (
                  <tr
                    key={item.id}
                    className="border-t border-border hover:bg-muted/30"
                    data-item-id={item.id}
                    data-item-status={item.status}
                  >
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        aria-label={`Selecionar item ${item.id}`}
                        checked={selectedItemIds.has(item.id)}
                        onChange={() => toggleItem(item.id)}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <span className="text-xs">
                        {EXECUTION_ITEM_STATUS_LABEL[item.status]}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {item.nsu ?? "—"}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {item.chave_nfse ? item.chave_nfse.slice(0, 16) + "…" : "—"}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {item.cnpj_emitente ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatValor(item.valor)}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {item.error_code ? (
                        <span title={item.error_message ?? undefined}>
                          {item.error_code}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {itemsTotalPages > 1 ? (
          <footer className="flex items-center justify-between border-t border-border px-4 py-2 text-xs">
            <span>
              Pagina {itemsPage} de {itemsTotalPages}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={itemsPage <= 1}
                onClick={() => setItemsPage((p) => Math.max(1, p - 1))}
                className="rounded-md border border-border px-2 py-1 disabled:opacity-50"
              >
                Anterior
              </button>
              <button
                type="button"
                disabled={itemsPage >= itemsTotalPages}
                onClick={() => setItemsPage((p) => p + 1)}
                className="rounded-md border border-border px-2 py-1 disabled:opacity-50"
              >
                Proxima
              </button>
            </div>
          </footer>
        ) : null}
      </section>
    </div>
  );
}
