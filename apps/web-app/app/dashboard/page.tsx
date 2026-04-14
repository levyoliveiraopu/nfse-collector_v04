import { FileText, ShieldCheck, Clock, CheckCircle2 } from "lucide-react";

type Kpi = {
  label: string;
  value: string;
  hint: string;
  icon: typeof FileText;
};

const KPIS: Kpi[] = [
  {
    label: "NFS-e coletadas (30d)",
    value: "—",
    hint: "Sem dados ainda",
    icon: FileText,
  },
  {
    label: "Certificados ativos",
    value: "—",
    hint: "Nenhum cadastrado",
    icon: ShieldCheck,
  },
  {
    label: "Coletas em andamento",
    value: "—",
    hint: "Nenhuma em execucao",
    icon: Clock,
  },
  {
    label: "Coletas concluidas hoje",
    value: "—",
    hint: "Sem historico",
    icon: CheckCircle2,
  },
];

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
        {KPIS.map((kpi) => {
          const Icon = kpi.icon;
          return (
            <article
              key={kpi.label}
              className="rounded-lg border border-border bg-card p-4 text-card-foreground shadow-sm"
            >
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {kpi.label}
                </p>
                <Icon
                  className="h-4 w-4 text-muted-foreground"
                  aria-hidden="true"
                />
              </div>
              <p className="mt-3 text-3xl font-semibold tracking-tight">
                {kpi.value}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">{kpi.hint}</p>
            </article>
          );
        })}
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
