"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import {
  acceptInvitationSchema,
  type AcceptInvitationInput,
} from "@/lib/users/schemas";
import { acceptInvitation, ApiError } from "@/lib/users/api-client";
import { AuthShell } from "@/components/auth/auth-shell";
import { FormField } from "@/components/auth/form-field";
import { cn } from "@/lib/utils";

export default function AceitarConvitePage({
  params,
}: {
  params: { token: string };
}) {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<AcceptInvitationInput>({
    resolver: zodResolver(acceptInvitationSchema),
    defaultValues: { name: "", password: "", confirm: "" },
  });

  async function onSubmit(values: AcceptInvitationInput) {
    setServerError(null);
    try {
      await acceptInvitation({
        token: params.token,
        name: values.name,
        password: values.password,
      });
      toast.success("Convite aceito. Bem-vindo!");
      router.replace("/dashboard");
    } catch (err) {
      const msg = extractMessage(err);
      setServerError(msg);
      toast.error(msg);
    }
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
        {serverError ? (
          <p role="alert" className="text-sm text-destructive">
            {serverError}
          </p>
        ) : null}
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
    </AuthShell>
  );
}

function extractMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.detail && typeof err.detail === "object" && "detail" in err.detail) {
      const detail = (err.detail as { detail?: unknown }).detail;
      if (typeof detail === "string") return detail;
    }
    if (err.status === 410) return "Convite expirado ou invalido.";
    if (err.status === 409) return "Este convite ja foi aceito.";
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return "Erro ao aceitar convite.";
}
