"use client";

import * as React from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";

export function ConfirmDialogDemo() {
  const [simpleOpen, setSimpleOpen] = React.useState(false);
  const [destructiveOpen, setDestructiveOpen] = React.useState(false);

  return (
    <div className="flex flex-wrap gap-3">
      <button
        type="button"
        onClick={() => setSimpleOpen(true)}
        className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90"
      >
        Abrir confirmacao simples
      </button>
      <button
        type="button"
        onClick={() => setDestructiveOpen(true)}
        className="inline-flex h-9 items-center rounded-md bg-destructive px-4 text-sm font-medium text-destructive-foreground shadow-sm hover:opacity-90"
      >
        Abrir confirmacao destrutiva
      </button>

      <ConfirmDialog
        open={simpleOpen}
        onClose={() => setSimpleOpen(false)}
        onConfirm={() => {
          toast.success("Acao confirmada");
          setSimpleOpen(false);
        }}
        title="Pausar agendamento"
        description="O cron fica suspenso ate voce retomar manualmente."
        confirmLabel="Pausar"
      />

      <ConfirmDialog
        open={destructiveOpen}
        onClose={() => setDestructiveOpen(false)}
        onConfirm={() => {
          toast.success("Empresa excluida (demo)");
          setDestructiveOpen(false);
        }}
        title="Excluir empresa ACME"
        description="Esta acao e irreversivel. Todas as execucoes e arquivos serao removidos apos 90 dias."
        confirmPhrase="ACME"
        tone="destructive"
        confirmLabel="Excluir empresa"
      />
    </div>
  );
}
