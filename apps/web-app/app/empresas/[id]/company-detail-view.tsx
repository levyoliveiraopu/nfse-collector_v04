"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronLeft } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError } from "@/lib/auth/api-client";
import {
  COMPANY_STATUS_LABEL,
  formatCnpj,
  getCompany,
  type Company,
} from "@/lib/api/companies";

import { CompanyTabs } from "./company-tabs";

function statusVariant(status: Company["status"]) {
  switch (status) {
    case "active":
      return "success" as const;
    case "paused":
      return "pending" as const;
    case "disabled":
    default:
      return "blocked" as const;
  }
}

export interface CompanyDetailViewProps {
  companyId: string;
}

export function CompanyDetailView({ companyId }: CompanyDetailViewProps) {
  const { accessToken, refresh } = useAuth();

  const query = useQuery<Company, ApiError>({
    queryKey: ["empresas:detail", companyId],
    queryFn: () =>
      getCompany(companyId, {
        accessToken,
        onTokenRefreshed: () => {
          void refresh();
        },
      }),
    retry: (failureCount, error) => {
      // Nao retentar em 4xx que nao seja 401 (apiFetch ja tenta refresh).
      if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
        return false;
      }
      return failureCount < 2;
    },
  });

  return (
    <div className="flex flex-col gap-6">
      <Link
        href="/empresas"
        className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Voltar para empresas
      </Link>

      {query.isPending ? (
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
          Carregando empresa...
        </div>
      ) : query.isError ? (
        <DetailError error={query.error} />
      ) : (
        <>
          <header className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="font-mono text-sm text-muted-foreground tabular-nums">
                {formatCnpj(query.data.cnpj)}
              </p>
              <h1 className="text-2xl font-semibold tracking-tight">
                {query.data.razao_social}
              </h1>
              {query.data.nome_fantasia ? (
                <p className="text-sm text-muted-foreground">
                  {query.data.nome_fantasia}
                </p>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                {query.data.uf}
              </span>
              <StatusBadge
                variant={statusVariant(query.data.status)}
                label={COMPANY_STATUS_LABEL[query.data.status]}
                size="sm"
              />
            </div>
          </header>

          <CompanyTabs company={query.data} />
        </>
      )}
    </div>
  );
}

function DetailError({ error }: { error: ApiError | Error }) {
  const isApi = error instanceof ApiError;
  const status = isApi ? error.status : null;
  const isNotFound = status === 404;
  const isForbidden = status === 403;
  const message = isNotFound
    ? "Empresa nao encontrada ou foi removida."
    : isForbidden
      ? "Voce nao tem permissao para acessar esta empresa."
      : "Nao foi possivel carregar os dados da empresa.";
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
