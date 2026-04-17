import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { ExecucaoDetailView } from "./execucao-detail-view";

export const metadata = {
  title: "Detalhe da execucao — NFS-e SaaS",
};

export default function ExecucaoDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return (
    <div className="flex flex-col gap-6">
      <nav aria-label="Voltar">
        <Link
          href="/execucoes"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          Voltar para execucoes
        </Link>
      </nav>

      <ExecucaoDetailView executionId={params.id} />
    </div>
  );
}
