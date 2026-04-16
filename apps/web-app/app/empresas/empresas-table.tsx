"use client";

import { useMemo } from "react";
import Link from "next/link";
import type { ColumnDef } from "@tanstack/react-table";

import { useAuth } from "@/components/auth/auth-provider";
import { DataTable, type FilterSchema } from "@/components/ui/data-table";
import { StatusBadge } from "@/components/ui/status-badge";

import {
  COMPANY_STATUS_LABEL,
  formatCnpj,
  listCompanies,
  type Company,
} from "@/lib/api/companies";

export const EMPRESAS_QUERY_KEY = "empresas:list";

const STATUS_OPTIONS = [
  { value: "active", label: COMPANY_STATUS_LABEL.active },
  { value: "paused", label: COMPANY_STATUS_LABEL.paused },
  { value: "disabled", label: COMPANY_STATUS_LABEL.disabled },
];

const FILTER_SCHEMA: FilterSchema[] = [
  { kind: "select", key: "status", label: "Status", options: STATUS_OPTIONS },
  // UF como text input de 2 letras (campo curto). Backend faz uppercase.
  { kind: "text", key: "uf", label: "UF", placeholder: "Ex: SP" },
];

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

function formatDateTime(iso: string | null): string {
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

export function EmpresasTable() {
  const { accessToken, refresh } = useAuth();

  const columns = useMemo<ColumnDef<Company, unknown>[]>(
    () => [
      {
        id: "cnpj",
        header: "CNPJ",
        // Mantemos o link no CNPJ por ser identificador estavel mesmo
        // se a razao social mudar.
        cell: ({ row }) => (
          <Link
            href={`/empresas/${row.original.id}`}
            className="font-mono text-sm tabular-nums text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {formatCnpj(row.original.cnpj)}
          </Link>
        ),
        enableSorting: false,
      },
      {
        id: "razao_social",
        header: "Razao social",
        cell: ({ row }) => (
          <span className="text-sm">{row.original.razao_social}</span>
        ),
        enableSorting: false,
      },
      {
        id: "uf",
        header: "UF",
        cell: ({ row }) => row.original.uf,
        enableSorting: false,
      },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => (
          <StatusBadge
            variant={statusVariant(row.original.status)}
            label={COMPANY_STATUS_LABEL[row.original.status]}
            size="sm"
          />
        ),
        enableSorting: false,
      },
      {
        id: "last_success_at",
        header: "Ultimo sucesso",
        // API-05 ainda nao suporta filtro/sort por last_success_at —
        // apresentamos como coluna informacional apenas. Ticket futuro
        // pode estender o backend para `?last_success_after=...`.
        cell: ({ row }) => (
          <span className="text-sm text-muted-foreground tabular-nums">
            {formatDateTime(row.original.last_success_at)}
          </span>
        ),
        enableSorting: false,
      },
      {
        id: "created_at",
        header: "Cadastrada em",
        cell: ({ row }) => (
          <span className="text-sm text-muted-foreground tabular-nums">
            {formatDateTime(row.original.created_at)}
          </span>
        ),
        enableSorting: false,
      },
    ],
    [],
  );

  return (
    <DataTable<Company>
      columns={columns}
      queryKey={EMPRESAS_QUERY_KEY}
      filterSchema={FILTER_SCHEMA}
      csvFilename="empresas"
      emptyMessage="Nenhuma empresa cadastrada ainda. Clique em 'Nova empresa' para comecar."
      fetcher={(params) =>
        listCompanies(params, {
          accessToken,
          onTokenRefreshed: () => {
            void refresh();
          },
        })
      }
    />
  );
}
