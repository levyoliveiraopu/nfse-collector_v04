import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { NovaExecucaoForm } from "./nova-execucao-form";

export const metadata = {
  title: "Nova execucao — NFS-e SaaS",
};

export default function NovaExecucaoPage() {
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <nav aria-label="Voltar">
        <Link
          href="/execucoes"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          Voltar para execucoes
        </Link>
      </nav>

      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Nova execucao</h1>
        <p className="text-sm text-muted-foreground">
          Selecione empresas, periodo e inicie a coleta de NFS-e.
        </p>
      </header>

      <NovaExecucaoForm />
    </div>
  );
}
