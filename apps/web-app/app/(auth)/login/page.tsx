"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { ApiError } from "@/lib/auth/api-client";
import { loginSchema, type LoginInput } from "@/lib/auth/schemas";
import { AuthShell } from "@/components/auth/auth-shell";
import { FormField } from "@/components/auth/form-field";
import { useAuth } from "@/components/auth/auth-provider";
import { cn } from "@/lib/utils";

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginPageFallback />}>
      <LoginPageContent />
    </Suspense>
  );
}

function LoginPageFallback() {
  return (
    <AuthShell title="Entrar" subtitle="Acesse o painel da sua operacao NFS-e.">
      <p className="text-sm text-muted-foreground" role="status">
        Carregando...
      </p>
    </AuthShell>
  );
}

function LoginPageContent() {
  const router = useRouter();
  const params = useSearchParams();
  const redirectTo = params.get("next") ?? "/dashboard";
  const { login } = useAuth();
  const [submitting, setSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginInput>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "", tenant_slug: "" },
  });

  async function onSubmit(values: LoginInput) {
    setSubmitting(true);
    try {
      await login({
        email: values.email,
        password: values.password,
        ...(values.tenant_slug ? { tenant_slug: values.tenant_slug } : {}),
      });
      router.replace(redirectTo);
    } catch (err) {
      const detail =
        err instanceof ApiError && typeof err.detail === "object" && err.detail
          ? (err.detail as { detail?: string }).detail
          : undefined;
      toast.error(detail ?? "Nao foi possivel entrar. Verifique suas credenciais.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Entrar"
      subtitle="Acesse o painel da sua operacao NFS-e."
      footer={
        <span>
          Nao tem conta?{" "}
          <Link href="/signup" className="font-medium text-primary hover:underline">
            Criar conta
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
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="voce@empresa.com"
          error={errors.email?.message}
          {...register("email")}
        />
        <FormField
          label="Senha"
          type="password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...register("password")}
        />
        <FormField
          label="Slug do tenant (opcional)"
          type="text"
          autoComplete="organization"
          placeholder="acme-contabil"
          error={errors.tenant_slug?.message}
          {...register("tenant_slug")}
        />
        <div className="flex justify-end -mt-2">
          <Link
            href="/recuperar-senha"
            className="text-xs text-muted-foreground hover:text-foreground hover:underline"
          >
            Esqueci minha senha
          </Link>
        </div>
        <button
          type="submit"
          disabled={submitting}
          className={cn(
            "mt-2 inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition",
            "hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            "disabled:cursor-not-allowed disabled:opacity-60",
          )}
        >
          {submitting ? "Entrando..." : "Entrar"}
        </button>
      </form>
    </AuthShell>
  );
}
