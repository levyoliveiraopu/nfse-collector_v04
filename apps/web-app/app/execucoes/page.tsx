import Link from "next/link";
import { Plus } from "lucide-react";

import { ExecucoesList } from "./execucoes-list";

export const metadata = {
  title: "Execucoes — NFS-e SaaS",
};

export default function ExecucoesPage() {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Execucoes</h1>
          <p className="text-sm text-muted-foreground">
            Coletas de NFS-e disparadas manualmente ou por agendamento.
          </p>
        </div>
        <Link
          href="/execucoes/nova"
          className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          Nova execucao
        </Link>
      </header>

      <ExecucoesList />
    </div>
  );
}
