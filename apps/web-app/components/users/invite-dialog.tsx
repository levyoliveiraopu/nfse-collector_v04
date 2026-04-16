"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Modal } from "./modal";
import { RoleSelect } from "./role-select";
import {
  inviteMemberSchema,
  rolesAssignableBy,
  type InviteMemberInput,
} from "@/lib/users/schemas";
import type { Role } from "@/lib/users/types";
import { cn } from "@/lib/utils";

type InviteDialogProps = {
  open: boolean;
  onClose: () => void;
  actorRole: Role;
  /** Retorna promise — usada para exibir loading / erros. */
  onSubmit: (input: InviteMemberInput) => Promise<void>;
};

/**
 * Modal de convite de novo membro. Respeita o RBAC do ator no select de
 * papel (admin so pode convidar operator/viewer). Em submit exitoso,
 * fecha o modal; em erro, exibe a mensagem devolvida pela API.
 */
export function InviteDialog({
  open,
  onClose,
  actorRole,
  onSubmit,
}: InviteDialogProps) {
  const defaultRole: Role = rolesAssignableBy(actorRole)[0] ?? "viewer";
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<InviteMemberInput>({
    resolver: zodResolver(inviteMemberSchema),
    defaultValues: { email: "", role: defaultRole },
  });

  React.useEffect(() => {
    if (open) reset({ email: "", role: defaultRole });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const selectedRole = watch("role");

  async function onValid(values: InviteMemberInput) {
    try {
      await onSubmit(values);
      toast.success(`Convite enviado para ${values.email}.`);
      onClose();
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Falha ao enviar convite.";
      toast.error(msg);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Convidar usuario"
      description="O convite sera enviado por email com um link de validade limitada."
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={handleSubmit(onValid)}
        noValidate
      >
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">Email</span>
          <input
            type="email"
            autoComplete="email"
            {...register("email")}
            className={cn(
              "h-9 rounded-md border border-border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              errors.email && "border-destructive focus-visible:ring-destructive",
            )}
            aria-invalid={errors.email ? "true" : undefined}
            aria-describedby={errors.email ? "invite-email-err" : undefined}
          />
          {errors.email ? (
            <span
              id="invite-email-err"
              role="alert"
              className="text-xs text-destructive"
            >
              {errors.email.message}
            </span>
          ) : null}
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">Papel</span>
          <RoleSelect
            value={selectedRole}
            actor={actorRole}
            onChange={(role) => setValue("role", role)}
            aria-label="Papel do usuario convidado"
          />
          {errors.role ? (
            <span role="alert" className="text-xs text-destructive">
              {errors.role.message}
            </span>
          ) : null}
        </label>

        <div className="mt-2 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex h-9 items-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground shadow-sm transition hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? "Enviando..." : "Enviar convite"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
