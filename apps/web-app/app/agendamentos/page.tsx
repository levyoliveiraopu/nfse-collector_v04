import { AgendamentosView } from "./agendamentos-view";

export const metadata = {
  title: "Agendamentos — NFS-e SaaS",
};

export default function AgendamentosPage() {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Agendamentos
          </h1>
          <p className="text-sm text-muted-foreground">
            Coletas automaticas por cron. Todas as empresas ou por CNPJ
            especifico; horario respeita a timezone informada.
          </p>
        </div>
      </header>

      <AgendamentosView />
    </div>
  );
}
