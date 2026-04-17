"use client";

import { useMemo } from "react";
import Link from "next/link";
import type { ColumnDef } from "@tanstack/react-table";

import { useAuth } from "@/components/auth/auth-provider";
import { DataTable, type FilterSchema } from "@/components/ui/data-table";
import { StatusBadge } from "@/components/ui/status-badge";

import {
  listOccurrences,
  OCCURRENCE_SEVERITY_LABEL,
  OCCURRENCE_STATUS_LABEL,
  type Occurrence,
  type OccurrenceSeverity,
  type OccurrenceStatus,
} from "@/lib/api/occurrences";
import { codeLabel } from "@/lib/occurrences/codes";

export const OCORRENCIAS_QUERY_KEY = "ocorrencias:list";

const STATUS_OPTIONS = (
  ["open", "ack", "snoozed", "resolved", "ignored"] satisfies OccurrenceStatus[]
).map((value) => ({ value, label: OCCURRENCE_STATUS_LABEL[value] }));

const SEVERITY_OPTIONS = (
  ["info", "warning", "error", "critical"] satisfies OccurrenceSeverity[]
).map((value) => ({ value, label: OCCURRENCE_SEVERITY_LABEL[value] }));

const FILTER_SCHEMA: FilterSchema[] = [
  { kind: "select", key: "status", label: "Status", options: STATUS_OPTIONS },
  {
    kind: "select",
    key: "severity",
    label: "Severidade",
    options: SEVERITY_OPTIONS,
  },
  {
    kind: "text",
    key: "company_id",
    label: "Empresa (UUID)",
    placeholder: "Cole o ID da empresa",
  },
];

export function statusVariant(status: OccurrenceStatus) {
  switch (status) {
    case "open":
      return "warning" as const;
    case "ack":
      return "processing" as const;
    case "snoozed":
      return "pending" as const;
    case "resolved":
      return "success" as const;
    case "ignored":
    default:
      return "blocked" as const;
  }
}

export function severityVariant(severity: OccurrenceSeverity) {
  switch (severity) {
    case "info":
      return "pending" as const;
    case "warning":
      return "warning" as const;
    case "error":
    case "critical":
    default:
      return "failed" as const;
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

export function OcorrenciasTable() {
  const { accessToken, refresh } = useAuth();

  const columns = useMemo<ColumnDef<Occurrence, unknown>[]>(
    () => [
      {
        id: "code",
        header: "Codigo",
        cell: ({ row }) => (
          <Link
            href={`/ocorrencias/${row.original.id}`}
            className="flex flex-col text-sm text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="font-mono text-xs tracking-tight">
              {row.original.code}
            </span>
            <span className="text-muted-foreground">
              {codeLabel(row.original.code)}
            </span>
          </Link>
        ),
        enableSorting: false,
      },
      {
        id: "severity",
        header: "Severidade",
        cell: ({ row }) => (
          <StatusBadge
            variant={severityVariant(row.original.severity)}
            label={OCCURRENCE_SEVERITY_LABEL[row.original.severity]}
            size="sm"
          />
        ),
        enableSorting: false,
      },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => (
          <StatusBadge
            variant={statusVariant(row.original.status)}
            label={OCCURRENCE_STATUS_LABEL[row.original.status]}
            size="sm"
          />
        ),
        enableSorting: false,
      },
      {
        id: "title",
        header: "Titulo",
        cell: ({ row }) => (
          <span className="text-sm" title={row.original.detail ?? undefined}>
            {row.original.title}
          </span>
        ),
        enableSorting: false,
      },
      {
        id: "last_seen_at",
        header: "Ultima ocorrencia",
        cell: ({ row }) => (
          <span className="text-sm text-muted-foreground tabular-nums">
            {formatDateTime(row.original.last_seen_at)}
          </span>
        ),
        enableSorting: false,
      },
      {
        id: "first_seen_at",
        header: "Primeira",
        cell: ({ row }) => (
          <span className="text-sm text-muted-foreground tabular-nums">
            {formatDateTime(row.original.first_seen_at)}
          </span>
        ),
        enableSorting: false,
      },
    ],
    [],
  );

  return (
    <DataTable<Occurrence>
      columns={columns}
      queryKey={OCORRENCIAS_QUERY_KEY}
      filterSchema={FILTER_SCHEMA}
      csvFilename="ocorrencias"
      emptyMessage="Nenhuma ocorrencia encontrada com os filtros atuais."
      fetcher={(params) =>
        listOccurrences(params, {
          accessToken,
          onTokenRefreshed: () => {
            void refresh();
          },
        })
      }
    />
  );
}
