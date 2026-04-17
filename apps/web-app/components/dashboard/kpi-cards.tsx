"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertOctagon,
  CheckCircle2,
  FileText,
  ShieldCheck,
} from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { KPIStatCard } from "@/components/ui/kpi-stat-card";

import {
  listExecutions,
  periodDateToUtcIso,
  type ExecutionListResponse,
} from "@/lib/api/executions";
import { listOccurrences } from "@/lib/api/occurrences";
import type { PeriodRange } from "@/lib/date/period";

interface KPICardsProps {
  period: PeriodRange;
}

/**
 * Janela derivada do `PeriodRange` em ISO 8601 UTC. A API trata `to`
 * como exclusivo (`started_at < to`), entao `to` avanca 1 dia.
 */
function periodToApiWindow(period: PeriodRange): { from: string; to: string } {
  return {
    from: periodDateToUtcIso(period.from, "start"),
    to: periodDateToUtcIso(period.to, "endExclusive"),
  };
}

const APPROX_LIMIT = 100;

function sumItemsOk(payload: ExecutionListResponse): {
  value: number;
  approx: boolean;
} {
  const sum = payload.items.reduce((acc, e) => acc + (e.items_ok ?? 0), 0);
  return { value: sum, approx: payload.total > payload.items.length };
}

function formatInt(value: number, approx = false): string {
  const formatted = new Intl.NumberFormat("pt-BR").format(value);
  return approx ? `${formatted}+` : formatted;
}

export function KPICards({ period }: KPICardsProps) {
  const { accessToken, refresh } = useAuth();
  const window = periodToApiWindow(period);

  const ctx = {
    accessToken,
    onTokenRefreshed: () => {
      void refresh();
    },
  };

  // KPI 1 — Notas coletadas no periodo (soma `items_ok` da primeira pagina;
  // quando `total > APPROX_LIMIT` marcamos como aproximado e sinalizamos
  // no hint. Follow-up: endpoint de agregacao em API-08.
  const notasQuery = useQuery({
    queryKey: ["dashboard:notas", period.from, period.to],
    queryFn: ({ signal }) =>
      listExecutions(
        { ...window, page: 1, page_size: APPROX_LIMIT },
        { ...ctx, signal },
      ),
    enabled: Boolean(accessToken),
  });

  // KPI 2 — Execucoes ok / total no periodo. Duas chamadas leves
  // (page_size=1) retornam `total` do envelope.
  const execTotalQuery = useQuery({
    queryKey: ["dashboard:exec-total", period.from, period.to],
    queryFn: ({ signal }) =>
      listExecutions(
        { ...window, page: 1, page_size: 1 },
        { ...ctx, signal },
      ),
    enabled: Boolean(accessToken),
  });
  const execOkQuery = useQuery({
    queryKey: ["dashboard:exec-ok", period.from, period.to],
    queryFn: ({ signal }) =>
      listExecutions(
        { ...window, page: 1, page_size: 1, status: "succeeded" },
        { ...ctx, signal },
      ),
    enabled: Boolean(accessToken),
  });

  // KPI 3 — Ocorrencias abertas (contagem sem filtro de periodo — inbox
  // reflete estado atual, nao a janela do dashboard).
  const ocorrenciasQuery = useQuery({
    queryKey: ["dashboard:ocorrencias-open"],
    queryFn: ({ signal }) =>
      listOccurrences(
        { status: "open", page: 1, page_size: 1 },
        { ...ctx, signal },
      ),
    enabled: Boolean(accessToken),
  });

  // KPI 4 — Certificados a vencer em 30d: API-06 popula
  // `company_credentials.cert_not_after` mas ainda NAO expoe listagem
  // REST. O card fica em `empty` com hint ate follow-up destravar.
  // Rastreio: follow-up "listagem de credenciais" (ADR-compat).

  const notas = notasQuery.data ? sumItemsOk(notasQuery.data) : null;

  return (
    <section
      aria-label="Indicadores principais"
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
    >
      <KPIStatCard
        title="Notas coletadas no periodo"
        icon={FileText}
        state={
          notasQuery.isPending
            ? "loading"
            : notasQuery.isError
              ? "error"
              : notas && notas.value === 0
                ? "empty"
                : "ready"
        }
        value={notas ? formatInt(notas.value, notas.approx) : undefined}
        hint={
          notas?.approx
            ? "Soma aproximada (agregacao server-side em follow-up)."
            : "Soma de items_ok das execucoes no periodo."
        }
        errorMessage="Falha ao carregar notas coletadas."
      />

      <KPIStatCard
        title="Execucoes OK / total"
        icon={CheckCircle2}
        state={
          execTotalQuery.isPending || execOkQuery.isPending
            ? "loading"
            : execTotalQuery.isError || execOkQuery.isError
              ? "error"
              : execTotalQuery.data && execTotalQuery.data.total === 0
                ? "empty"
                : "ready"
        }
        value={
          execTotalQuery.data && execOkQuery.data
            ? `${formatInt(execOkQuery.data.total)} / ${formatInt(execTotalQuery.data.total)}`
            : undefined
        }
        hint="Execucoes concluidas vs total no periodo."
        errorMessage="Falha ao carregar execucoes."
      />

      <KPIStatCard
        title="Ocorrencias abertas"
        icon={AlertOctagon}
        state={
          ocorrenciasQuery.isPending
            ? "loading"
            : ocorrenciasQuery.isError
              ? "error"
              : ocorrenciasQuery.data && ocorrenciasQuery.data.total === 0
                ? "empty"
                : "ready"
        }
        value={
          ocorrenciasQuery.data
            ? formatInt(ocorrenciasQuery.data.total)
            : undefined
        }
        hint="Estado atual do inbox (nao filtrado por periodo)."
        errorMessage="Falha ao carregar ocorrencias."
      />

      <KPIStatCard
        title="Certificados a vencer (30d)"
        icon={ShieldCheck}
        state="empty"
        hint="Disponivel apos endpoint REST de credenciais (follow-up)."
      />
    </section>
  );
}
