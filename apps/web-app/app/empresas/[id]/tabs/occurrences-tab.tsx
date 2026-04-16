"use client";

import { AlertCircle } from "lucide-react";

import type { Company } from "@/lib/api/companies";

/**
 * Stub da aba "Ocorrencias". Schema ja existe (DATA-04). UI de
 * listagem/triagem chega em APP-06 (com runbooks ja documentados em
 * DOCS-03 e DOCS-04).
 */
export function OccurrencesTab({ company }: { company: Company }) {
  return (
    <div
      className="flex items-start gap-3 rounded-lg border border-border bg-card p-6 text-sm shadow-sm"
      data-tab-content="occurrences"
      data-company-id={company.id}
    >
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <div>
        <p className="font-medium">Ocorrencias chegam em APP-06</p>
        <p className="mt-1 text-muted-foreground">
          A tabela <code className="font-mono">occurrences</code> ja existe
          (DATA-04), com runbooks de credencial invalida (DOCS-03) e portal
          indisponivel (DOCS-04). A UI de triagem sera entregue em APP-06.
        </p>
      </div>
    </div>
  );
}
