"use client";

import { Info } from "lucide-react";

import type { Company } from "@/lib/api/companies";

/**
 * Stub da aba "Execucoes". O endpoint da listagem de execucoes por
 * company e entregue em API-07 (collector REST); o fluxo completo de
 * filtros/DataTable depende de APP-05.
 */
export function ExecutionsTab({ company }: { company: Company }) {
  return (
    <div
      className="flex items-start gap-3 rounded-lg border border-border bg-card p-6 text-sm shadow-sm"
      data-tab-content="executions"
      data-company-id={company.id}
    >
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <div>
        <p className="font-medium">Execucoes ainda nao disponiveis</p>
        <p className="mt-1 text-muted-foreground">
          A listagem de execucoes por CNPJ sera liberada junto com APP-05
          (pagina <code className="font-mono">/execucoes</code>) e o endpoint
          REST de execucoes (ticket API-07).
        </p>
      </div>
    </div>
  );
}
