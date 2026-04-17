"use client";

import Link from "next/link";
import { AlertCircle, ArrowRight } from "lucide-react";

import type { Company } from "@/lib/api/companies";

/**
 * Aba "Ocorrencias" do detalhe de empresa.
 *
 * APP-06 entrega o inbox global em `/ocorrencias`. Aqui mantemos apenas
 * um call-to-action que abre o inbox pre-filtrado pelo `company_id`,
 * aproveitando o filtro `company_id` que a `DataTable` ja persiste na
 * URL via `?company_id=...`. Um widget inline com lista/acoes por
 * empresa fica como extensao para um ticket de UX futuro.
 */
export function OccurrencesTab({ company }: { company: Company }) {
  const href = {
    pathname: "/ocorrencias",
    query: { company_id: company.id },
  };
  return (
    <div
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-6 text-sm shadow-sm"
      data-tab-content="occurrences"
      data-company-id={company.id}
    >
      <div className="flex items-start gap-3">
        <AlertCircle
          className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
        <div>
          <p className="font-medium">Ocorrencias operacionais</p>
          <p className="mt-1 text-muted-foreground">
            Abra o inbox de ocorrencias filtrado por esta empresa para
            triar, reconhecer, resolver ou reprocessar. O runbook de cada
            codigo aparece inline no detalhe.
          </p>
        </div>
      </div>
      <div>
        <Link
          href={href}
          className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border bg-background px-3 text-sm font-medium shadow-sm transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Abrir no inbox
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Link>
      </div>
    </div>
  );
}
