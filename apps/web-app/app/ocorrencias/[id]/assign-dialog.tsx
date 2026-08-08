"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AlertTriangle } from "lucide-react";

import { Modal } from "@/components/ui/modal";
import { ApiError } from "@/lib/auth/api-client";

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const SCHEMA = z.object({
  assignee_user_id: z
    .string()
    .trim()
    .min(1, "Informe o ID do usuario.")
    .regex(UUID_REGEX, "Precisa ser um UUID valido."),
});

type FormData = z.infer<typeof SCHEMA>;

export interface AssignDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (assigneeUserId: string) => void;
  pending: boolean;
  error: ApiError | Error | null;
}

/**
 * Atribui a ocorrencia a um membro do tenant. Esta entrega aceita o
 * UUID digitado manualmente — um seletor rico com lista de usuarios
 * (dependencia: endpoint `GET /users` dentro do tenant) fica para um
 * ticket futuro. O backend valida que o user e membro do tenant e
 * devolve 404 quando nao for.
 */
export function AssignDialog({
  open,
  onClose,
  onSubmit,
  pending,
  error,
}: AssignDialogProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<FormData>({
    resolver: zodResolver(SCHEMA),
    defaultValues: { assignee_user_id: "" },
  });

  React.useEffect(() => {
    if (open) {
      reset({ assignee_user_id: "" });
    }
  }, [open, reset]);

  function submit(data: FormData) {
    onSubmit(data.assignee_user_id.trim());
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Atribuir ocorrencia"
      description="Informe o UUID do usuario do tenant."
    >
      <form onSubmit={handleSubmit(submit)} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label htmlFor="assign-user-id" className="text-sm font-medium">
            User ID <span className="text-destructive">*</span>
          </label>
          <input
            id="assign-user-id"
            aria-describedby={
              errors.assignee_user_id ? undefined : "assign-user-help"
            }
            type="text"
            autoComplete="off"
            spellCheck={false}
            disabled={pending}
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            {...register("assignee_user_id")}
            className="h-9 rounded-md border border-border bg-background px-3 text-sm font-mono shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
          />
          {errors.assignee_user_id ? (
            <p className="text-xs text-destructive">
              {errors.assignee_user_id.message}
            </p>
          ) : (
            <p id="assign-user-help" className="text-xs text-muted-foreground">
              Cole o UUID da tabela `/usuarios` (ticket futuro traz o
              seletor).
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
            {pending ? "Atribuindo..." : "Atribuir"}
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
  if (status === 404) {
    msg = "Usuario nao e membro deste tenant.";
  } else if (status === 403) {
    msg = "Voce nao tem permissao para atribuir ocorrencias.";
  } else if (status === 422) {
    msg = "UUID invalido.";
  } else {
    msg = "Nao foi possivel atribuir a ocorrencia agora. Tente novamente.";
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
