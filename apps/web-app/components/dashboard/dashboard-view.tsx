"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertOctagon, Play } from "lucide-react";

import { PeriodPicker } from "@/components/ui/period-picker";
import { computePresetRange, type PeriodRange } from "@/lib/date/period";

import { KPICards } from "./kpi-cards";
import { RecentTimeline } from "./recent-timeline";

/**
 * View cliente do `/dashboard` (APP-02). Concentra:
 * - filtro de periodo global (presets + custom), controlado localmente
 *   (estado por sessao de navegacao — persistencia em URL fica como
 *   follow-up);
 * - 4 KPIStatCards (DS-05);
 * - timeline das ultimas 10 execucoes;
 * - atalhos "Nova execucao" e "Ver ocorrencias" (rotas entregues em
 *   APP-05/APP-06; seguem o mesmo padrao dos placeholders em
 *   `nav-items.ts`).
 */
export function DashboardView() {
  const [period, setPeriod] = useState<PeriodRange>(() =>
    computePresetRange("current_month"),
  );

  return (
    <div className="flex flex-col gap-6" data-help-id="dashboard-primary">
      <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Visao geral da operacao NFS-e do tenant.
          </p>
        </div>
        <div className="flex flex-col items-stretch gap-2 md:flex-row md:items-start">
          <Link
            href="/execucoes/nova"
            className="inline-flex h-9 items-center justify-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Play className="h-4 w-4" aria-hidden="true" />
            Nova execucao
          </Link>
          <Link
            href="/ocorrencias"
            className="inline-flex h-9 items-center justify-center gap-1.5 rounded-md border border-input bg-background px-3 text-sm font-medium shadow-sm transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <AlertOctagon className="h-4 w-4" aria-hidden="true" />
            Ver ocorrencias
          </Link>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
        <PeriodPicker value={period} onChange={setPeriod} />
      </div>

      <KPICards period={period} />

      <RecentTimeline period={period} />
    </div>
  );
}
