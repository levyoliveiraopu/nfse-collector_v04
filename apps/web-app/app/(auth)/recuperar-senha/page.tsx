"use client";

import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import {
  recoverPasswordSchema,
  type RecoverPasswordInput,
} from "@/lib/auth/schemas";
import { AuthShell } from "@/components/auth/auth-shell";
import { FormField } from "@/components/auth/form-field";
import { cn } from "@/lib/utils";

export default function RecuperarSenhaPage() {
  const [submitted, setSubmitted] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RecoverPasswordInput>({
    resolver: zodResolver(recoverPasswordSchema),
    defaultValues: { email: "" },
  });

  async function onSubmit(_values: RecoverPasswordInput) {
    // API-XX (password recovery) ainda nao disponivel. Confirmamos a
    // submissao no client para manter o fluxo coerente quando o back for
    // plugado; nao vazamos se o email existe.
    toast.info(
      "Se o email estiver cadastrado, voce recebera instrucoes. (Envio real sera habilitado em breve.)",
    );
    setSubmitted(true);
  }

  return (
    <AuthShell
      title="Recuperar senha"
      subtitle="Informe o email da sua conta para receber as instrucoes."
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
          Se o email estiver cadastrado, voce recebera um link para redefinir a
          senha em instantes.
        </div>
      ) : (
        <form
          className="flex flex-col gap-4"
          onSubmit={handleSubmit(onSubmit)}
          noValidate
        >
          <FormField
            label="Email"
            type="email"
            autoComplete="email"
            error={errors.email?.message}
            {...register("email")}
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
            {isSubmitting ? "Enviando..." : "Enviar instrucoes"}
          </button>
        </form>
      )}
    </AuthShell>
  );
}
