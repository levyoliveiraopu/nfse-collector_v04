"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AlertTriangle } from "lucide-react";

import { Modal } from "@/components/ui/modal";
import { ApiError } from "@/lib/auth/api-client";

const SCHEMA = z.object({
  note: z
    .string()
    .trim()
    .min(1, "A nota e obrigatoria.")
    .max(2000, "A nota deve ter no maximo 2000 caracteres."),
});

type FormData = z.infer<typeof SCHEMA>;

export interface ResolveDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (note: string) => void;
  pending: boolean;
  error: ApiError | Error | null;
}

export function ResolveDialog({
  open,
  onClose,
  onSubmit,
  pending,
  error,
}: ResolveDialogProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<FormData>({
    resolver: zodResolver(SCHEMA),
    defaultValues: { note: "" },
  });

  // Reset do form quando o modal (re)abre para evitar rastros da abertura
  // anterior.
  React.useEffect(() => {
    if (open) {
      reset({ note: "" });
    }
  }, [open, reset]);

  function submit(data: FormData) {
    onSubmit(data.note.trim());
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Resolver ocorrencia"
      description="Descreva a acao tomada. A nota e gravada no audit log."
    >
      <form onSubmit={handleSubmit(submit)} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label htmlFor="resolve-note" className="text-sm font-medium">
            Nota <span className="text-destructive">*</span>
          </label>
          <textarea
            id="resolve-note"
            aria-describedby={errors.note ? undefined : "resolve-note-help"}
            rows={4}
            placeholder="Ex.: reprocessei execucao xyz; todos os NSUs foram recuperados."
            disabled={pending}
            {...register("note")}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
          />
          {errors.note ? (
            <p className="text-xs text-destructive">{errors.note.message}</p>
          ) : (
            <p id="resolve-note-help" className="text-xs text-muted-foreground">
              Descreva a correção e o resultado sem incluir senhas, tokens ou
              dados fiscais desnecessários. A nota fica na auditoria.
            </p>
          )}
        </div>

        {error ? <SubmitError error={error} /> : null}

        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={pending}
            className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={pending || !isDirty}
            className="inline-flex h-9 items-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
          >
            {pending ? "Resolvendo..." : "Resolver"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function SubmitError({ error }: { error: ApiError | Error }) {
  const isApi = error instanceof ApiError;
  const status = isApi ? error.status : null;
  let msg: string;
  if (status === 409) {
    msg =
      "A ocorrencia nao aceita resolve no estado atual (ja foi ignorada ou terminal).";
  } else if (status === 422) {
    msg = "Nota invalida (vazia ou muito longa).";
  } else if (status === 403) {
    msg = "Voce nao tem permissao para resolver ocorrencias.";
  } else {
    msg = "Nao foi possivel resolver a ocorrencia agora. Tente novamente.";
  }
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{msg}</span>
    </div>
  );
}
