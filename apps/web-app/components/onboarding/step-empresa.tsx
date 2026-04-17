"use client";

/**
 * Passo 1 do wizard (APP-11): cadastrar a 1a empresa.
 *
 * Form inline (nao usa `<NovaEmpresaDialog>` para evitar modal dentro
 * de modal). O schema reproduz o do dialog entregue em APP-03; a
 * duplicacao e deliberada — nao queremos refatorar aquele componente
 * como efeito colateral deste ticket. Ao criar com sucesso,
 * `onCreated(company)` avanca o wizard.
 */
import * as React from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AlertTriangle, Loader2 } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { CNPJInput } from "@/components/ui/cnpj-input";
import { isValidCnpj, normalizeCnpj } from "@/lib/validators/cnpj";
import { ApiError } from "@/lib/auth/api-client";
import {
  createCompany,
  type Company,
  type CompanyCreatePayload,
} from "@/lib/api/companies";

const UFS = [
  "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA",
  "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
  "RO", "RR", "RS", "SC", "SE", "SP", "TO",
] as const;

const schema = z.object({
  cnpj: z
    .string()
    .transform((v) => normalizeCnpj(v))
    .refine((v) => v.length === 14, "CNPJ deve ter 14 digitos")
    .refine((v) => isValidCnpj(v), "CNPJ invalido"),
  razao_social: z.string().trim().min(2, "Informe a razao social").max(200),
  municipio_ibge: z
    .string()
    .trim()
    .min(1, "Codigo IBGE do municipio obrigatorio")
    .max(10)
    .regex(/^\d+$/, "Apenas digitos"),
  uf: z
    .string()
    .transform((v) => v.toUpperCase())
    .refine((v) => (UFS as readonly string[]).includes(v), "UF invalida"),
});

type FormValues = z.infer<typeof schema>;

export interface StepEmpresaProps {
  onCreated: (company: Company) => void;
}

export function StepEmpresa({ onCreated }: StepEmpresaProps) {
  const { accessToken, refresh } = useAuth();
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  const {
    control,
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      cnpj: "",
      razao_social: "",
      municipio_ibge: "",
      uf: "",
    },
  });

  async function onSubmit(values: FormValues) {
    setSubmitError(null);
    const payload: CompanyCreatePayload = {
      cnpj: values.cnpj,
      razao_social: values.razao_social,
      municipio_ibge: values.municipio_ibge,
      uf: values.uf,
    };
    try {
      const created = await createCompany(payload, {
        accessToken,
        onTokenRefreshed: () => {
          void refresh();
        },
      });
      onCreated(created);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setSubmitError("CNPJ ja cadastrado neste tenant.");
        } else if (err.status === 403) {
          setSubmitError(
            "Voce nao tem permissao para criar empresas. Peca a um owner/admin.",
          );
        } else {
          setSubmitError("Nao foi possivel criar a empresa. Tente novamente.");
        }
      } else {
        setSubmitError("Erro de rede. Verifique a conexao e tente novamente.");
      }
    }
  }

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="flex flex-col gap-4"
      noValidate
      data-testid="onboarding-step-empresa"
    >
      <p className="text-sm text-muted-foreground">
        Cadastre o primeiro CNPJ que vai ter NFS-e coletadas automaticamente.
        Voce pode adicionar mais depois em <strong>/empresas</strong>.
      </p>

      <div className="flex flex-col gap-1">
        <label htmlFor="onb-cnpj" className="text-sm font-medium">
          CNPJ
        </label>
        <Controller
          name="cnpj"
          control={control}
          render={({ field }) => (
            <CNPJInput
              id="onb-cnpj"
              value={field.value}
              onChange={field.onChange}
              onBlur={field.onBlur}
              aria-invalid={errors.cnpj ? true : undefined}
            />
          )}
        />
        {errors.cnpj ? (
          <p role="alert" className="text-xs text-destructive">
            {errors.cnpj.message}
          </p>
        ) : null}
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="onb-razao" className="text-sm font-medium">
          Razao social
        </label>
        <input
          id="onb-razao"
          type="text"
          autoComplete="off"
          maxLength={200}
          aria-invalid={errors.razao_social ? true : undefined}
          {...register("razao_social")}
          className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        {errors.razao_social ? (
          <p role="alert" className="text-xs text-destructive">
            {errors.razao_social.message}
          </p>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_120px]">
        <div className="flex flex-col gap-1">
          <label htmlFor="onb-municipio" className="text-sm font-medium">
            Codigo IBGE do municipio
          </label>
          <input
            id="onb-municipio"
            type="text"
            inputMode="numeric"
            autoComplete="off"
            maxLength={10}
            placeholder="Ex: 3550308"
            aria-invalid={errors.municipio_ibge ? true : undefined}
            {...register("municipio_ibge")}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          {errors.municipio_ibge ? (
            <p role="alert" className="text-xs text-destructive">
              {errors.municipio_ibge.message}
            </p>
          ) : null}
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="onb-uf" className="text-sm font-medium">
            UF
          </label>
          <select
            id="onb-uf"
            aria-invalid={errors.uf ? true : undefined}
            {...register("uf")}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="">—</option>
            {UFS.map((uf) => (
              <option key={uf} value={uf}>
                {uf}
              </option>
            ))}
          </select>
          {errors.uf ? (
            <p role="alert" className="text-xs text-destructive">
              {errors.uf.message}
            </p>
          ) : null}
        </div>
      </div>

      {submitError ? (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
          data-testid="onb-empresa-error"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{submitError}</span>
        </div>
      ) : null}

      <div className="flex items-center justify-end">
        <button
          type="submit"
          disabled={isSubmitting}
          className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {isSubmitting ? (
            <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
          ) : null}
          {isSubmitting ? "Salvando…" : "Cadastrar empresa"}
        </button>
      </div>
    </form>
  );
}
