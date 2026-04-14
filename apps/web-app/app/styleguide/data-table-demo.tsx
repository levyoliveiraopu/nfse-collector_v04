"use client";

import * as React from "react";
import type { ColumnDef } from "@tanstack/react-table";

import { DataTable } from "@/components/ui/data-table";
import type {
  FetchParams,
  FetchResult,
  FilterSchema,
} from "@/components/ui/data-table";
import { StatusBadge } from "@/components/ui/status-badge";

// -------------------------------------------------------------------
// Dataset mock: 10.000 linhas de NFS-e ficticias. Gerado uma unica vez
// por sessao do browser (seed deterministico via Math.random no useMemo).
// -------------------------------------------------------------------

interface Nota {
  id: string;
  chave: string;
  razao_social: string;
  municipio: string;
  valor: number;
  data_emissao: string; // ISO date (YYYY-MM-DD)
  status:
    | "success"
    | "processing"
    | "pending"
    | "failed"
    | "reprocess_needed";
}

const MUNICIPIOS = [
  "Sao Paulo",
  "Rio de Janeiro",
  "Belo Horizonte",
  "Curitiba",
  "Porto Alegre",
  "Salvador",
  "Recife",
  "Fortaleza",
  "Brasilia",
  "Manaus",
];

const RAZOES = [
  "Alpha Servicos",
  "Bravo Engenharia",
  "Charlie Consultoria",
  "Delta Logistica",
  "Echo Tecnologia",
  "Foxtrot Juridico",
  "Golf Financeira",
  "Hotel Saude",
  "India Educacional",
  "Juliet Construcoes",
];

const STATUSES: Nota["status"][] = [
  "success",
  "processing",
  "pending",
  "failed",
  "reprocess_needed",
];

function pseudoRandom(seed: number): () => number {
  // Mulberry32 — determinismo estavel por sessao.
  let t = seed;
  return function () {
    t = (t + 0x6d2b79f5) | 0;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

function makeDataset(total: number): Nota[] {
  const rng = pseudoRandom(42);
  const rows: Nota[] = [];
  const today = new Date();
  for (let i = 0; i < total; i++) {
    const daysBack = Math.floor(rng() * 365);
    const d = new Date(today);
    d.setDate(d.getDate() - daysBack);
    const iso = d.toISOString().slice(0, 10);
    rows.push({
      id: String(i + 1).padStart(6, "0"),
      chave: `NFSE-${String(i + 1).padStart(8, "0")}`,
      razao_social: RAZOES[Math.floor(rng() * RAZOES.length)]!,
      municipio: MUNICIPIOS[Math.floor(rng() * MUNICIPIOS.length)]!,
      valor: Math.round(rng() * 50000 * 100) / 100,
      data_emissao: iso,
      status: STATUSES[Math.floor(rng() * STATUSES.length)]!,
    });
  }
  return rows;
}

// -------------------------------------------------------------------
// Fetcher mock server-side: filtra/ordena/pagina em memoria e simula
// uma latencia de rede.
// -------------------------------------------------------------------

function applyFilters(data: Nota[], params: FetchParams): Nota[] {
  const { filters } = params;
  let out = data;
  const q = (filters.q as string | undefined)?.trim().toLowerCase();
  if (q) {
    out = out.filter(
      (r) =>
        r.razao_social.toLowerCase().includes(q) ||
        r.chave.toLowerCase().includes(q) ||
        r.id.includes(q),
    );
  }
  const municipio = filters.municipio as string | undefined;
  if (municipio) out = out.filter((r) => r.municipio === municipio);
  const status = filters.status as string | undefined;
  if (status) out = out.filter((r) => r.status === status);
  const periodo = filters.periodo as
    | { from?: string | null; to?: string | null }
    | undefined;
  if (periodo?.from) out = out.filter((r) => r.data_emissao >= periodo.from!);
  if (periodo?.to) out = out.filter((r) => r.data_emissao <= periodo.to!);
  return out;
}

function applySort(data: Nota[], params: FetchParams): Nota[] {
  if (!params.sort) return data;
  const { id, desc } = params.sort;
  const sign = desc ? -1 : 1;
  return [...data].sort((a, b) => {
    const av = (a as unknown as Record<string, unknown>)[id];
    const bv = (b as unknown as Record<string, unknown>)[id];
    if (av === bv) return 0;
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    if (typeof av === "number" && typeof bv === "number") {
      return (av - bv) * sign;
    }
    return String(av).localeCompare(String(bv), "pt-BR") * sign;
  });
}

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

// -------------------------------------------------------------------
// Componente de demo
// -------------------------------------------------------------------

export function DataTableDemo() {
  const dataset = React.useMemo(() => makeDataset(10_000), []);

  const fetcher = React.useCallback(
    async (params: FetchParams): Promise<FetchResult<Nota>> => {
      // Simula latencia de rede.
      await new Promise((r) => setTimeout(r, 180));
      const filtered = applySort(applyFilters(dataset, params), params);
      const { pageIndex, pageSize } = params.pagination;
      const start = pageIndex * pageSize;
      return {
        rows: filtered.slice(start, start + pageSize),
        total: filtered.length,
      };
    },
    [dataset],
  );

  const columns = React.useMemo<ColumnDef<Nota, unknown>[]>(
    () => [
      { id: "id", accessorKey: "id", header: "ID" },
      { id: "chave", accessorKey: "chave", header: "Chave NFS-e" },
      {
        id: "razao_social",
        accessorKey: "razao_social",
        header: "Razao social",
      },
      { id: "municipio", accessorKey: "municipio", header: "Municipio" },
      {
        id: "valor",
        accessorKey: "valor",
        header: "Valor",
        cell: ({ row }) => (
          <span className="tabular-nums">
            {formatBRL(row.original.valor)}
          </span>
        ),
      },
      {
        id: "data_emissao",
        accessorKey: "data_emissao",
        header: "Emissao",
        cell: ({ row }) => (
          <span className="tabular-nums">
            {formatDate(row.original.data_emissao)}
          </span>
        ),
      },
      {
        id: "status",
        accessorKey: "status",
        header: "Status",
        enableSorting: false,
        cell: ({ row }) => (
          <StatusBadge variant={row.original.status} size="sm" />
        ),
      },
    ],
    [],
  );

  const filterSchema: FilterSchema[] = React.useMemo(
    () => [
      {
        kind: "text",
        key: "q",
        label: "Buscar",
        placeholder: "razao social / chave / id",
      },
      {
        kind: "select",
        key: "municipio",
        label: "Municipio",
        options: MUNICIPIOS.map((m) => ({ value: m, label: m })),
      },
      {
        kind: "select",
        key: "status",
        label: "Status",
        options: [
          { value: "success", label: "Sucesso" },
          { value: "processing", label: "Processando" },
          { value: "pending", label: "Pendente" },
          { value: "failed", label: "Falhou" },
          { value: "reprocess_needed", label: "Reprocessar" },
        ],
      },
      {
        kind: "date-range",
        key: "periodo",
        label: "Periodo de emissao",
      },
    ],
    [],
  );

  return (
    <DataTable<Nota>
      queryKey="styleguide-notas"
      columns={columns}
      fetcher={fetcher}
      filterSchema={filterSchema}
      urlPrefix="dt."
      csvFilename="nfse-demo"
      defaultPageSize={25}
    />
  );
}
