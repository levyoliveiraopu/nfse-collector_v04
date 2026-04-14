"use client";

import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import {
  acceptInviteSchema,
  type AcceptInviteInput,
} from "@/lib/auth/schemas";
import { AuthShell } from "@/components/auth/auth-shell";
import { FormField } from "@/components/auth/form-field";
import { cn } from "@/lib/utils";

export default function AceitarConvitePage({
  params,
}: {
  params: { token: string };
}) {
  const [submitted, setSubmitted] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<AcceptInviteInput>({
    resolver: zodResolver(acceptInviteSchema),
    defaultValues: { name: "", password: "", confirm: "" },
  });

  async function onSubmit(_values: AcceptInviteInput) {
    // API-XX (invites) ainda nao disponivel. Form valida e aceita os dados;
    // submissao real sera plugada quando o endpoint existir.
    toast.info(
      "Convite aceito. O back-end de convites sera habilitado em breve.",
    );
    setSubmitted(true);
  }

  const tokenPreview = params.token ? `${params.token.slice(0, 8)}...` : "";

  return (
    <AuthShell
      title="Aceitar convite"
      subtitle={
        tokenPreview
          ? `Token: ${tokenPreview}`
          : "Defina seu nome e senha para acessar a conta."
      }
      footer={
        <span>
          <Link href="/login" className="font-medium text-primary hover:underline">
            Voltar para o login
          </Link>
        </span>
      }
    >
      {submitted ? (
        <div
          role="status"
          aria-live="polite"
          className="rounded-md border border-border bg-muted/40 p-4 text-sm text-muted-foreground"
        >
          Convite aceito. Faca login para acessar o painel.
        </div>
      ) : (
        <form
          className="flex flex-col gap-4"
          onSubmit={handleSubmit(onSubmit)}
          noValidate
        >
          <FormField
            label="Seu nome"
            autoComplete="name"
            error={errors.name?.message}
            {...register("name")}
          />
          <FormField
            label="Senha"
            type="password"
            autoComplete="new-password"
            description="Minimo 10 caracteres."
            error={errors.password?.message}
            {...register("password")}
          />
          <FormField
            label="Confirmar senha"
            type="password"
            autoComplete="new-password"
            error={errors.confirm?.message}
            {...register("confirm")}
          />
          <button
            type="submit"
            disabled={isSubmitting}
            className={cn(
              "mt-2 inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition",
              "hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              "disabled:cursor-not-allowed disabled:opacity-60",
            )}
          >
            {isSubmitting ? "Salvando..." : "Aceitar convite"}
          </button>
        </form>
      )}
    </AuthShell>
  );
}
