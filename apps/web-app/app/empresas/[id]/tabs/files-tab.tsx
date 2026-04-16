"use client";

import { FolderOpen } from "lucide-react";

import type { Company } from "@/lib/api/companies";

/**
 * Stub da aba "Arquivos". Schema da tabela `files` existe desde DATA-05
 * (sem `storage_tier`, ADR-003). Endpoints REST de listagem/download
 * com presigned URL ficam para APP-07 / API-10.
 */
export function FilesTab({ company }: { company: Company }) {
  return (
    <div
      className="flex items-start gap-3 rounded-lg border border-border bg-card p-6 text-sm shadow-sm"
      data-tab-content="files"
      data-company-id={company.id}
    >
      <FolderOpen className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <div>
        <p className="font-medium">Arquivos chegam em APP-07</p>
        <p className="mt-1 text-muted-foreground">
          A tabela <code className="font-mono">files</code> ja existe
          (DATA-05). A listagem dos XMLs/PDFs coletados, com retencao de
          90d (ADR-003), sera entregue em API-10 e APP-07.
        </p>
      </div>
    </div>
  );
}
