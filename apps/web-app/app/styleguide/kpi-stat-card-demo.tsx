"use client";

import {
  CheckCircle2,
  Clock,
  FileText,
  ShieldCheck,
  Zap,
} from "lucide-react";

import { KPIStatCard } from "@/components/ui/kpi-stat-card";

const trendUp = [12, 18, 15, 22, 27, 31, 34, 40];
const trendDown = [48, 44, 40, 41, 35, 30, 27, 24];
const trendFlat = [20, 22, 19, 21, 20, 22, 21, 20];

export function KPIStatCardDemo() {
  return (
    <div className="space-y-6">
      <section
        aria-label="KPIs em estado ready"
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
      >
        <KPIStatCard
          title="NFS-e coletadas (30d)"
          value="1.284"
          deltaPercent={12.4}
          trendData={trendUp}
          icon={FileText}
          hint="vs 30 dias anteriores"
        />
        <KPIStatCard
          title="Taxa de sucesso"
          value="97,2%"
          deltaPercent={-2.1}
          trendData={trendDown}
          icon={CheckCircle2}
          hint="vs 30 dias anteriores"
        />
        <KPIStatCard
          title="Coletas em andamento"
          value="6"
          deltaPercent={0}
          trendData={trendFlat}
          icon={Clock}
          hint="vs 30 dias anteriores"
        />
        <KPIStatCard
          title="Certificados ativos"
          value="12"
          icon={ShieldCheck}
          hint="Nenhum vencendo em 30d"
        />
      </section>

      <section
        aria-label="KPIs em estados auxiliares"
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"
      >
        <KPIStatCard
          title="Carregando"
          state="loading"
          icon={Zap}
        />
        <KPIStatCard
          title="Sem dados"
          state="empty"
          icon={FileText}
          hint="Nenhuma coleta no periodo"
        />
        <KPIStatCard
          title="Falha ao carregar"
          state="error"
          icon={FileText}
          errorMessage="API indisponivel. Tente novamente em instantes."
        />
      </section>
    </div>
  );
}
