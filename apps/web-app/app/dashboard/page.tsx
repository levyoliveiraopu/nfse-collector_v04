import { CheckCircle2, Clock, FileText, ShieldCheck } from "lucide-react";

import { KPIStatCard } from "@/components/ui/kpi-stat-card";

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Visao geral da sua operacao NFS-e. Dados reais aparecerao aqui apos a
          primeira coleta.
        </p>
      </div>

      <section
        aria-label="Indicadores principais"
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
      >
        <KPIStatCard
          title="NFS-e coletadas (30d)"
          state="empty"
          icon={FileText}
          hint="Sem dados ainda"
        />
        <KPIStatCard
          title="Certificados ativos"
          state="empty"
          icon={ShieldCheck}
          hint="Nenhum cadastrado"
        />
        <KPIStatCard
          title="Coletas em andamento"
          state="empty"
          icon={Clock}
          hint="Nenhuma em execucao"
        />
        <KPIStatCard
          title="Coletas concluidas hoje"
          state="empty"
          icon={CheckCircle2}
          hint="Sem historico"
        />
      </section>

      <section
        aria-label="Coletas recentes"
        className="rounded-lg border border-border bg-card text-card-foreground shadow-sm"
      >
        <header className="border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold">Coletas recentes</h2>
          <p className="text-xs text-muted-foreground">
            As ultimas execucoes do worker aparecerao aqui.
          </p>
        </header>
        <div className="flex items-center justify-center px-4 py-12 text-sm text-muted-foreground">
          Nenhuma coleta registrada ate o momento.
        </div>
      </section>
    </div>
  );
}
