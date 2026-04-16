"use client";

import { ShieldAlert } from "lucide-react";

import type { Company } from "@/lib/api/companies";

/**
 * Stub da aba "Credencial". O upload do PFX A1 (cifra AES-256-GCM) ja
 * existe no backend (API-06); a UI de upload + status + validade chega
 * em APP-04.
 */
export function CredentialTab({ company }: { company: Company }) {
  return (
    <div
      className="flex items-start gap-3 rounded-lg border border-border bg-card p-6 text-sm shadow-sm"
      data-tab-content="credential"
      data-company-id={company.id}
    >
      <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <div>
        <p className="font-medium">Upload de credencial chega em APP-04</p>
        <p className="mt-1 text-muted-foreground">
          O backend ja aceita upload de PFX A1 cifrado (API-06). A interface
          para enviar/visualizar/revogar a credencial sera entregue no
          ticket APP-04.
        </p>
      </div>
    </div>
  );
}
