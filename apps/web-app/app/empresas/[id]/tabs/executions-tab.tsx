"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Play } from "lucide-react";

import { StatusBadge } from "@/components/ui/status-badge";
import { useAuth } from "@/components/auth/auth-provider";
import type { Company } from "@/lib/api/companies";
import {
  EXECUTION_STATUS_LABEL,
  decideExecutionBadge,
  listExecutions,
} from "@/lib/api/executions";

const WRITE_ROLES = new Set(["owner", "admin", "operator"]);

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/**
 * Aba "Execucoes" da empresa (APP-03 + APP-05). Mostra as 5 execucoes
 * mais recentes da company e atalha para `/execucoes/nova` pre-selecionando
 * o CNPJ atual via query param.
 */
export function ExecutionsTab({ company }: { company: Company }) {
  const { user, accessToken, refresh } = useAuth();
  const canCreate = user ? WRITE_ROLES.has(user.role) : false;

  const query = useQuery({
    queryKey: ["execution:by-company", company.id],
    queryFn: () =>
      listExecutions(
        { companyId: company.id, pageSize: 5 },
        {
          accessToken,
          onTokenRefreshed: () => {
            void refresh();
          },
        },
      ),
    enabled: Boolean(accessToken),
  });

  const items = query.data?.items ?? [];

  return (
    <div
      className="flex flex-col gap-4"
      data-tab-content="executions"
      data-company-id={company.id}
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">Ultimas execucoes</h2>
          <p className="text-xs text-muted-foreground">
            5 mais recentes desta empresa.
          </p>
        </div>
        {canCreate ? (
          <Link
            href={`/execucoes/nova?company_id=${company.id}`}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90"
          >
            <Play className="h-3.5 w-3.5" aria-hidden="true" />
            Nova execucao
          </Link>
        ) : null}
      </header>

      {query.isLoading ? (
        <p className="text-sm text-muted-foreground" role="status">
          Carregando…
        </p>
      ) : query.isError ? (
        <p className="text-sm text-destructive" role="alert">
          Nao foi possivel carregar execucoes desta empresa.
        </p>
      ) : items.length === 0 ? (
        <p className="rounded-md border border-border bg-card p-4 text-sm text-muted-foreground">
          Nenhuma execucao registrada ainda para este CNPJ.
        </p>
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-md border border-border bg-card">
          {items.map((exec) => (
            <li
              key={exec.id}
              className="flex items-center justify-between gap-3 px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <StatusBadge
                  variant={decideExecutionBadge(exec.status)}
                  label={EXECUTION_STATUS_LABEL[exec.status]}
                  size="sm"
                />
                <div className="text-xs text-muted-foreground">
                  <div>
                    {exec.items_ok + exec.items_fail} / {exec.items_total} items
                  </div>
                  <div>{formatDate(exec.started_at)}</div>
                </div>
              </div>
              <Link
                href={`/execucoes/${exec.id}`}
                className="text-xs text-primary hover:underline"
              >
                Abrir
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
