"use client";

import * as React from "react";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Download,
  Save,
  Trash2,
} from "lucide-react";

import { cn } from "@/lib/utils";

import { buildCsv, downloadCsv, type CsvColumn } from "./csv";
import {
  deleteSavedFilter,
  listSavedFilters,
  saveFilter,
} from "./saved-filters";
import type {
  DataTablePagination,
  FetchParams,
  FetchResult,
  FilterSchema,
  FilterState,
  SavedFilter,
  SortState,
} from "./types";
import {
  parseState,
  serializeState,
  stripDataTableParams,
} from "./url-state";

// Referencia estavel para o default de `filterSchema` (evita recriar `[]`
// a cada render, o que invalidaria os `useMemo` dependentes).
const EMPTY_FILTER_SCHEMA: FilterSchema[] = [];

export interface DataTableProps<T> {
  /** Definicoes de coluna do TanStack Table. */
  columns: ColumnDef<T, unknown>[];
  /** Chave unica da tabela (react-query cache + localStorage saved filters). */
  queryKey: string;
  /** Fetcher server-side. */
  fetcher: (params: FetchParams) => Promise<FetchResult<T>>;
  /** Filtros habilitados. */
  filterSchema?: FilterSchema[];
  /** Prefixo para searchParams da URL (quando ha mais de uma tabela na rota). */
  urlPrefix?: string;
  /** Page size default (nao preservado na URL se for o default). */
  defaultPageSize?: number;
  /** Tamanhos de pagina oferecidos no seletor. */
  pageSizeOptions?: number[];
  /** Texto de estado vazio. */
  emptyMessage?: string;
  /** Mostrar botao de export CSV. */
  enableCsvExport?: boolean;
  /** Nome do arquivo CSV (sem extensao). */
  csvFilename?: string;
  /** Callback ao mudar filtros/sort/paginacao. */
  onStateChange?: (state: FetchParams) => void;
  /** Habilitar saved filters via localStorage. */
  enableSavedFilters?: boolean;
  /** Derivacao opcional de colunas de CSV (default: usa `columns`). */
  csvColumns?: CsvColumn<T>[];
  className?: string;
}

const DEFAULT_PAGE_SIZE = 25;
const DEFAULT_PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

interface HeaderMeta {
  id: string;
  label: string;
  canSort: boolean;
}

/**
 * DataTable (DS-06) — tabela reutilizavel com paginacao, filtragem e
 * ordenacao server-side, preservacao de estado em searchParams e
 * export CSV.
 *
 * O componente e agnostico de dominio: recebe `columns`, `fetcher` e
 * `filterSchema`. Integra-se com `@tanstack/react-query` (sem provider
 * proprio — e esperado que `AppQueryClientProvider` esteja na arvore).
 */
export function DataTable<T extends object>({
  columns,
  queryKey,
  fetcher,
  filterSchema = EMPTY_FILTER_SCHEMA,
  urlPrefix = "",
  defaultPageSize = DEFAULT_PAGE_SIZE,
  pageSizeOptions = DEFAULT_PAGE_SIZE_OPTIONS,
  emptyMessage = "Nenhum registro encontrado.",
  enableCsvExport = true,
  csvFilename,
  onStateChange,
  enableSavedFilters = true,
  csvColumns,
  className,
}: DataTableProps<T>) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // --- estado derivado da URL (fonte unica) ---------------------------
  // Dependemos do `.toString()` (primitivo) para nao reativar useMemo
  // toda vez que `useSearchParams()` devolver uma nova referencia.
  const searchParamsString = searchParams?.toString() ?? "";
  const urlState = React.useMemo(() => {
    const sp = new URLSearchParams(searchParamsString);
    return parseState(sp, filterSchema, {
      prefix: urlPrefix,
      defaultPageSize,
    });
  }, [searchParamsString, filterSchema, urlPrefix, defaultPageSize]);

  const pushUrl = React.useCallback(
    (next: {
      pagination: DataTablePagination;
      sort: SortState | null;
      filters: FilterState;
    }) => {
      const current = new URLSearchParams(searchParamsString);
      const without = stripDataTableParams(current, filterSchema, urlPrefix);
      const ours = serializeState(next, filterSchema, {
        prefix: urlPrefix,
        defaultPageSize,
      });
      ours.forEach((v, k) => without.set(k, v));
      const qs = without.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname ?? "", {
        scroll: false,
      });
      onStateChange?.(next);
    },
    [
      searchParamsString,
      filterSchema,
      urlPrefix,
      defaultPageSize,
      router,
      pathname,
      onStateChange,
    ],
  );

  // --- draft local dos filtros (aplicados com debounce/blur) ---------
  const [filterDraft, setFilterDraft] = React.useState<FilterState>(
    urlState.filters,
  );
  // Sincroniza o draft sempre que a URL mudar externamente, mas guardado
  // por comparacao estrutural para nao gerar loop: `urlState.filters` e
  // sempre um objeto novo, entao comparar por referencia dispararia
  // set-state a cada render.
  const urlFiltersKey = React.useMemo(
    () => JSON.stringify(urlState.filters),
    [urlState.filters],
  );
  React.useEffect(() => {
    setFilterDraft(urlState.filters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlFiltersKey]);

  // --- react-query ----------------------------------------------------
  const queryResult = useQuery({
    queryKey: [queryKey, urlState],
    queryFn: () => fetcher(urlState),
    placeholderData: keepPreviousData,
  });

  const rows = queryResult.data?.rows ?? [];
  const total = queryResult.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / urlState.pagination.pageSize));

  // --- TanStack Table --------------------------------------------------
  const sortingState: SortingState = urlState.sort
    ? [{ id: urlState.sort.id, desc: urlState.sort.desc }]
    : [];

  const table = useReactTable<T>({
    data: rows,
    columns,
    state: {
      sorting: sortingState,
      pagination: urlState.pagination,
    },
    manualPagination: true,
    manualSorting: true,
    manualFiltering: true,
    pageCount,
    getCoreRowModel: getCoreRowModel(),
  });

  // --- handlers -------------------------------------------------------
  function applyFilters() {
    pushUrl({
      pagination: { ...urlState.pagination, pageIndex: 0 },
      sort: urlState.sort,
      filters: filterDraft,
    });
  }

  function clearFilters() {
    setFilterDraft({});
    pushUrl({
      pagination: { ...urlState.pagination, pageIndex: 0 },
      sort: urlState.sort,
      filters: {},
    });
  }

  function onPageChange(pageIndex: number) {
    pushUrl({
      pagination: { ...urlState.pagination, pageIndex },
      sort: urlState.sort,
      filters: urlState.filters,
    });
  }

  function onPageSizeChange(size: number) {
    pushUrl({
      pagination: { pageIndex: 0, pageSize: size },
      sort: urlState.sort,
      filters: urlState.filters,
    });
  }

  function onToggleSort(colId: string) {
    const current = urlState.sort;
    let next: SortState | null;
    if (!current || current.id !== colId) next = { id: colId, desc: false };
    else if (!current.desc) next = { id: colId, desc: true };
    else next = null;
    pushUrl({
      pagination: { ...urlState.pagination, pageIndex: 0 },
      sort: next,
      filters: urlState.filters,
    });
  }

  function onExportCsv() {
    const cols: CsvColumn<T>[] =
      csvColumns ??
      columns
        .map((c) => {
          const id =
            (c as { id?: string }).id ??
            (c as { accessorKey?: string }).accessorKey ??
            "";
          const header =
            typeof c.header === "string" ? (c.header as string) : id;
          if (!id) return null;
          return { key: id, header } as CsvColumn<T>;
        })
        .filter((c): c is CsvColumn<T> => c !== null);
    const csv = buildCsv(rows, cols);
    const name = csvFilename ?? queryKey;
    downloadCsv(`${name}.csv`, csv);
  }

  // --- saved filters --------------------------------------------------
  const storageKey = `dt:${queryKey}`;
  const [saved, setSaved] = React.useState<SavedFilter[]>([]);
  React.useEffect(() => {
    if (enableSavedFilters) setSaved(listSavedFilters(storageKey));
  }, [enableSavedFilters, storageKey]);

  function onSaveCurrent() {
    const name = window.prompt("Nome do filtro salvo");
    if (!name) return;
    const entry = saveFilter(
      storageKey,
      name.trim(),
      urlState.filters,
      urlState.sort,
    );
    setSaved((s) => [entry, ...s.filter((e) => e.name !== entry.name)]);
  }

  function onApplySaved(id: string) {
    const entry = saved.find((e) => e.id === id);
    if (!entry) return;
    setFilterDraft(entry.filters);
    pushUrl({
      pagination: { ...urlState.pagination, pageIndex: 0 },
      sort: entry.sort,
      filters: entry.filters,
    });
  }

  function onDeleteSaved(id: string) {
    deleteSavedFilter(storageKey, id);
    setSaved((s) => s.filter((e) => e.id !== id));
  }

  // --- UI -------------------------------------------------------------
  const isLoading = queryResult.isPending;
  const isFetching = queryResult.isFetching;
  const isError = queryResult.isError;
  const pageIndex = urlState.pagination.pageIndex;
  const pageSize = urlState.pagination.pageSize;

  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-border bg-card text-card-foreground shadow-sm",
        className,
      )}
    >
      {filterSchema.length > 0 ? (
        <div className="flex flex-wrap items-end gap-3 border-b border-border p-3">
          {filterSchema.map((f) => (
            <FilterField
              key={f.key}
              schema={f}
              value={filterDraft[f.key]}
              onChange={(v) =>
                setFilterDraft((prev) => ({ ...prev, [f.key]: v }))
              }
              onApply={applyFilters}
            />
          ))}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={applyFilters}
              className="inline-flex h-9 items-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Aplicar
            </button>
            <button
              type="button"
              onClick={clearFilters}
              className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium text-foreground transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Limpar
            </button>
            {enableSavedFilters ? (
              <SavedFiltersMenu
                saved={saved}
                onSave={onSaveCurrent}
                onApply={onApplySaved}
                onDelete={onDeleteSaved}
              />
            ) : null}
            {enableCsvExport ? (
              <button
                type="button"
                onClick={onExportCsv}
                disabled={rows.length === 0}
                className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border bg-background px-3 text-sm font-medium text-foreground transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Exportar CSV"
              >
                <Download className="h-4 w-4" aria-hidden="true" />
                CSV
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="relative overflow-x-auto">
        <table className="w-full text-sm" role="table">
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id} className="border-b border-border">
                {group.headers.map((header) => {
                  const meta = resolveHeader(header);
                  const active = urlState.sort?.id === meta.id;
                  return (
                    <th
                      key={header.id}
                      scope="col"
                      className="whitespace-nowrap px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground"
                      aria-sort={
                        active
                          ? urlState.sort?.desc
                            ? "descending"
                            : "ascending"
                          : "none"
                      }
                    >
                      {meta.canSort ? (
                        <button
                          type="button"
                          onClick={() => onToggleSort(meta.id)}
                          className="inline-flex items-center gap-1 rounded-sm px-1 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <span>
                            {flexRender(
                              header.column.columnDef.header,
                              header.getContext(),
                            )}
                          </span>
                          <SortIcon
                            active={active}
                            desc={urlState.sort?.desc ?? false}
                          />
                        </button>
                      ) : (
                        flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody aria-busy={isFetching || undefined}>
            {isLoading ? (
              <SkeletonRows rows={pageSize} cols={columns.length} />
            ) : isError ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-3 py-10 text-center"
                >
                  <ErrorState
                    onRetry={() => queryResult.refetch()}
                    message={(queryResult.error as Error)?.message}
                  />
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-3 py-10 text-center text-sm text-muted-foreground"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className="border-b border-border last:border-b-0 hover:bg-accent/40"
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="whitespace-nowrap px-3 py-2 text-sm"
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border p-3 text-sm">
        <div className="flex items-center gap-2 text-muted-foreground">
          <label className="flex items-center gap-2">
            <span>Linhas por pagina:</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="h-8 rounded-md border border-border bg-background px-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {pageSizeOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </label>
          <span className="tabular-nums">
            {total === 0
              ? "0 de 0"
              : `${pageIndex * pageSize + 1}-${Math.min(
                  (pageIndex + 1) * pageSize,
                  total,
                )} de ${total}`}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onPageChange(Math.max(0, pageIndex - 1))}
            disabled={pageIndex === 0}
            aria-label="Pagina anterior"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border bg-background text-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </button>
          <span className="px-2 tabular-nums text-muted-foreground">
            {pageIndex + 1} / {pageCount}
          </span>
          <button
            type="button"
            onClick={() =>
              onPageChange(Math.min(pageCount - 1, pageIndex + 1))
            }
            disabled={pageIndex >= pageCount - 1}
            aria-label="Proxima pagina"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border bg-background text-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------
// Helpers internos
// ---------------------------------------------------------------------

function resolveHeader<T>(header: {
  id: string;
  column: { columnDef: ColumnDef<T, unknown> };
}): HeaderMeta {
  const def = header.column.columnDef;
  const label = typeof def.header === "string" ? (def.header as string) : header.id;
  // `enableSorting !== false` permite habilitar por padrao; o consumidor
  // opta por desligar ordenacao em colunas nao-server-sortable.
  const canSort = (def as { enableSorting?: boolean }).enableSorting !== false;
  return { id: header.id, label, canSort };
}

function SortIcon({ active, desc }: { active: boolean; desc: boolean }) {
  if (!active) {
    return (
      <ArrowUpDown
        aria-hidden="true"
        className="h-3.5 w-3.5 opacity-50"
      />
    );
  }
  return desc ? (
    <ArrowDown aria-hidden="true" className="h-3.5 w-3.5" />
  ) : (
    <ArrowUp aria-hidden="true" className="h-3.5 w-3.5" />
  );
}

function SkeletonRows({ rows, cols }: { rows: number; cols: number }) {
  const arr = Array.from({ length: Math.min(rows, 10) });
  return (
    <>
      {arr.map((_, i) => (
        <tr key={i} className="border-b border-border last:border-b-0">
          {Array.from({ length: cols }).map((__, j) => (
            <td key={j} className="px-3 py-2">
              <div
                aria-hidden="true"
                className="h-4 w-full animate-pulse rounded bg-muted"
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

function ErrorState({
  onRetry,
  message,
}: {
  onRetry: () => void;
  message?: string;
}) {
  return (
    <div
      role="alert"
      className="inline-flex flex-col items-center gap-2 text-sm text-destructive"
    >
      <div className="inline-flex items-center gap-2">
        <AlertTriangle aria-hidden="true" className="h-4 w-4" />
        <span>{message ?? "Nao foi possivel carregar os dados."}</span>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex h-8 items-center rounded-md border border-border bg-background px-3 text-sm font-medium text-foreground transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        Tentar novamente
      </button>
    </div>
  );
}

interface FilterFieldProps {
  schema: FilterSchema;
  value: FilterState[string];
  onChange: (v: FilterState[string]) => void;
  onApply: () => void;
}

function FilterField({ schema, value, onChange, onApply }: FilterFieldProps) {
  const baseLabel = (
    <span className="text-xs font-medium text-muted-foreground">
      {schema.label}
    </span>
  );

  if (schema.kind === "text") {
    return (
      <label className="flex flex-col gap-1">
        {baseLabel}
        <input
          type="text"
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onApply();
          }}
          placeholder={schema.placeholder}
          className="h-9 w-48 rounded-md border border-border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </label>
    );
  }

  if (schema.kind === "select") {
    return (
      <label className="flex flex-col gap-1">
        {baseLabel}
        <select
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value || null)}
          className="h-9 w-48 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">{schema.placeholder ?? "Todos"}</option>
          {schema.options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>
    );
  }

  // date-range
  const v = (value as { from?: string | null; to?: string | null } | undefined) ?? {};
  return (
    <fieldset className="flex flex-col gap-1">
      <legend className="text-xs font-medium text-muted-foreground">
        {schema.label}
      </legend>
      <div className="flex items-center gap-2">
        <input
          type="date"
          aria-label={`${schema.label} (de)`}
          value={v.from ?? ""}
          onChange={(e) => onChange({ ...v, from: e.target.value || null })}
          className="h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <span className="text-xs text-muted-foreground">ate</span>
        <input
          type="date"
          aria-label={`${schema.label} (ate)`}
          value={v.to ?? ""}
          onChange={(e) => onChange({ ...v, to: e.target.value || null })}
          className="h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>
    </fieldset>
  );
}

interface SavedFiltersMenuProps {
  saved: SavedFilter[];
  onSave: () => void;
  onApply: (id: string) => void;
  onDelete: (id: string) => void;
}

function SavedFiltersMenu({
  saved,
  onSave,
  onApply,
  onDelete,
}: SavedFiltersMenuProps) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border bg-background px-3 text-sm font-medium text-foreground transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Save className="h-4 w-4" aria-hidden="true" />
        Filtros salvos
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-30 mt-1 w-64 rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onSave();
            }}
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent focus-visible:outline-none focus-visible:bg-accent"
          >
            <Save className="h-4 w-4" aria-hidden="true" />
            Salvar filtro atual
          </button>
          {saved.length > 0 ? (
            <div className="my-1 h-px bg-border" aria-hidden="true" />
          ) : null}
          {saved.length === 0 ? (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">
              Nenhum filtro salvo.
            </p>
          ) : (
            <ul className="max-h-64 overflow-y-auto">
              {saved.map((entry) => (
                <li
                  key={entry.id}
                  className="flex items-center gap-1 rounded-sm px-1 py-0.5 hover:bg-accent"
                >
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setOpen(false);
                      onApply(entry.id);
                    }}
                    className="flex-1 truncate px-1 py-1 text-left text-sm"
                  >
                    {entry.name}
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(entry.id)}
                    aria-label={`Excluir filtro ${entry.name}`}
                    className="inline-flex h-7 w-7 items-center justify-center rounded-sm text-muted-foreground hover:bg-destructive/10 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
