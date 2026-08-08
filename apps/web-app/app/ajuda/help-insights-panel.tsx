"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/components/auth/auth-provider";
import { getHelpInsights, type HelpInsightCounts } from "@/lib/api/help";

const EMPTY_COUNTS: HelpInsightCounts = {
  article_opened: 0,
  search_performed: 0,
  search_no_results: 0,
  tour_started: 0,
  tour_completed: 0,
  tour_skipped: 0,
  tour_failed: 0,
  feedback_yes: 0,
  feedback_no: 0,
};

function percentage(numerator: number, denominator: number): string {
  if (denominator <= 0) return "0%";
  return `${Math.round((numerator / denominator) * 100)}%`;
}
export function HelpInsightsPanel() {
  const { accessToken, refresh } = useAuth();
  const [days, setDays] = useState<7 | 30 | 90>(30);
  const query = useQuery({
    queryKey: ["help:insights", days],
    queryFn: () =>
      getHelpInsights(
        {
          accessToken,
          onTokenRefreshed: () => {
            void refresh();
          },
        },
        days,
      ),
    enabled: Boolean(accessToken),
  });
  const totals = query.data?.totals ?? EMPTY_COUNTS;
  const metrics = useMemo(
    () => [
      { label: "Aberturas", value: totals.article_opened.toLocaleString("pt-BR") },
      {
        label: "Pesquisas sem resultado",
        value: percentage(totals.search_no_results, totals.search_performed),
      },
      {
        label: "Conclusão dos guias",
        value: percentage(totals.tour_completed, totals.tour_started),
      },
      {
        label: "Ajuda avaliada como útil",
        value: percentage(
          totals.feedback_yes,
          totals.feedback_yes + totals.feedback_no,
        ),
      },
    ],
    [totals],
  );

  return (
    <section className="border-t border-border pt-8" aria-labelledby="help-insights-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="help-insights-title" className="text-xl font-semibold">
            Insights da Ajuda
          </h2>
          <p className="text-sm text-muted-foreground">
            Contagens agregadas do tenant, sem usuário ou texto pesquisado.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Período</span>
          <select
            value={days}
            onChange={(event) => setDays(Number(event.target.value) as 7 | 30 | 90)}
            className="h-9 rounded-md border border-input bg-background px-2"
          >
            <option value={7}>7 dias</option>
            <option value={30}>30 dias</option>
            <option value={90}>90 dias</option>
          </select>
        </label>
      </div>

      {query.isLoading ? (
        <p className="mt-4 text-sm text-muted-foreground" role="status">
          Carregando indicadores…
        </p>
      ) : query.isError ? (
        <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm" role="alert">
          Não foi possível carregar os indicadores.
          <button
            type="button"
            onClick={() => query.refetch()}
            className="ml-2 font-medium text-primary underline"
          >
            Tentar novamente
          </button>
        </div>
      ) : (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {metrics.map((metric) => (
              <div key={metric.label} className="rounded-lg border border-border bg-card p-4 shadow-sm">
                <p className="text-xs text-muted-foreground">{metric.label}</p>
                <p className="mt-1 text-2xl font-semibold tabular-nums">{metric.value}</p>
              </div>
            ))}
          </div>

          <div className="mt-4 overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[680px] text-sm">
              <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">Artigo / rota</th>
                  <th className="px-3 py-2 text-right">Aberturas</th>
                  <th className="px-3 py-2 text-right">Guias concluídos</th>
                  <th className="px-3 py-2 text-right">Útil</th>
                  <th className="px-3 py-2 text-right">Não útil</th>
                </tr>
              </thead>
              <tbody>
                {(query.data?.rows ?? []).map((row) => (
                  <tr key={`${row.article_slug}:${row.route_key}`} className="border-t border-border">
                    <td className="px-3 py-2">
                      <span className="font-medium">{row.article_slug || "Pesquisa"}</span>
                      <span className="ml-2 text-xs text-muted-foreground">{row.route_key}</span>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{row.article_opened}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{row.tour_completed}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{row.feedback_yes}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{row.feedback_no}</td>
                  </tr>
                ))}
                {(query.data?.rows.length ?? 0) === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-3 py-8 text-center text-muted-foreground">
                      Ainda não há eventos neste período.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
