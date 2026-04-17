"use client";

import { Inbox } from "lucide-react";
import { toast } from "sonner";

import { EmptyState } from "@/components/ui/empty-state";

export function EmptyStateDemo() {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <EmptyState
        title="Sem empresas cadastradas"
        description="Adicione a primeira empresa para comecar a coletar NFS-e."
        icon={Inbox}
        action={{
          label: "Cadastrar empresa",
          onClick: () => toast.message("CTA clicado"),
        }}
      />
      <EmptyState
        title="Nenhum arquivo gerado"
        description="Quando uma execucao concluir, os arquivos aparecem aqui."
      />
    </div>
  );
}
