"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { ApiError } from "@/lib/auth/api-client";
import { signupSchema, type SignupInput } from "@/lib/auth/schemas";
import { AuthShell } from "@/components/auth/auth-shell";
import { FormField } from "@/components/auth/form-field";
import { useAuth } from "@/components/auth/auth-provider";
import { cn } from "@/lib/utils";

export default function SignupPage() {
  const router = useRouter();
  const { signup } = useAuth();
  const [submitting, setSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignupInput>({
    resolver: zodResolver(signupSchema),
    defaultValues: {
      tenant_name: "",
      tenant_slug: "",
      name: "",
      email: "",
      password: "",
      accept_terms: false as unknown as true,
    },
  });

  async function onSubmit(values: SignupInput) {
    setSubmitting(true);
    try {
      const { accept_terms: _ignored, ...payload } = values;
      void _ignored;
      await signup(payload);
      router.replace("/dashboard");
    } catch (err) {
      const detail =
        err instanceof ApiError && typeof err.detail === "object" && err.detail
          ? (err.detail as { detail?: string }).detail
          : undefined;
      toast.error(detail ?? "Nao foi possivel criar a conta.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Criar conta"
      subtitle="Registre sua empresa e comece a coletar NFS-e."
      footer={
        <span>
          Ja tem conta?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Entrar
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
          label="Nome da empresa"
          autoComplete="organization"
          error={errors.tenant_name?.message}
          {...register("tenant_name")}
        />
        <FormField
          label="Identificador (slug)"
          description="Usado em URLs e convites. Apenas letras minusculas, numeros e hifens."
          placeholder="acme-contabil"
          error={errors.tenant_slug?.message}
          {...register("tenant_slug")}
        />
        <FormField
          label="Seu nome"
          autoComplete="name"
          error={errors.name?.message}
          {...register("name")}
        />
        <FormField
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register("email")}
        />
        <FormField
          label="Senha"
          type="password"
          autoComplete="new-password"
          description="Minimo 10 caracteres."
          error={errors.password?.message}
          {...register("password")}
        />

        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 rounded border-input text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-invalid={errors.accept_terms ? "true" : undefined}
            {...register("accept_terms")}
          />
          <span className="text-muted-foreground">
            Li e aceito os{" "}
            <Link href="/legal" className="text-primary hover:underline">
              Termos de Uso
            </Link>{" "}
            e a{" "}
            <Link href="/legal" className="text-primary hover:underline">
              Politica de Privacidade
            </Link>
            .
          </span>
        </label>
        {errors.accept_terms ? (
          <p className="-mt-2 text-xs text-destructive">
            {errors.accept_terms.message}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={submitting}
          className={cn(
            "mt-2 inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition",
            "hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            "disabled:cursor-not-allowed disabled:opacity-60",
          )}
        >
          {submitting ? "Criando conta..." : "Criar conta"}
        </button>
      </form>
    </AuthShell>
  );
}
