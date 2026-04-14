import type {
  DataTablePagination,
  FilterSchema,
  FilterState,
  FilterValue,
  SortState,
} from "./types";

/**
 * Serializacao bi-direcional do estado da DataTable em `URLSearchParams`,
 * usada para preservar filtros/paginacao/ordenacao na URL (DoD DS-06).
 *
 * Convencao de chaves (com um prefixo opcional para nao colidir quando
 * houver mais de uma tabela na mesma rota):
 *   <prefix>page      -> page index (1-based na URL para melhor UX)
 *   <prefix>size      -> page size
 *   <prefix>sort      -> "<colId>:asc" | "<colId>:desc"
 *   <prefix>f.<key>   -> filtro (texto ou select)
 *   <prefix>f.<key>.from / <prefix>f.<key>.to -> filtro date-range (ISO)
 */

export interface UrlStateShape {
  pagination: DataTablePagination;
  sort: SortState | null;
  filters: FilterState;
}

export interface SerializeOptions {
  prefix?: string;
  defaultPageSize?: number;
}

const DEFAULT_PAGE_SIZE = 25;

function k(prefix: string, name: string): string {
  return prefix ? `${prefix}${name}` : name;
}

/** Retorna a URL sem os parametros controlados pela DataTable. */
export function stripDataTableParams(
  params: URLSearchParams,
  schema: FilterSchema[],
  prefix = "",
): URLSearchParams {
  const next = new URLSearchParams(params);
  next.delete(k(prefix, "page"));
  next.delete(k(prefix, "size"));
  next.delete(k(prefix, "sort"));
  for (const f of schema) {
    if (f.kind === "date-range") {
      next.delete(k(prefix, `f.${f.key}.from`));
      next.delete(k(prefix, `f.${f.key}.to`));
    } else {
      next.delete(k(prefix, `f.${f.key}`));
    }
  }
  return next;
}

export function serializeState(
  state: UrlStateShape,
  schema: FilterSchema[],
  { prefix = "", defaultPageSize = DEFAULT_PAGE_SIZE }: SerializeOptions = {},
): URLSearchParams {
  const out = new URLSearchParams();
  const pageOneBased = state.pagination.pageIndex + 1;
  if (pageOneBased > 1) {
    out.set(k(prefix, "page"), String(pageOneBased));
  }
  if (state.pagination.pageSize !== defaultPageSize) {
    out.set(k(prefix, "size"), String(state.pagination.pageSize));
  }
  if (state.sort) {
    out.set(
      k(prefix, "sort"),
      `${state.sort.id}:${state.sort.desc ? "desc" : "asc"}`,
    );
  }
  for (const def of schema) {
    const raw = state.filters[def.key];
    if (raw === undefined || raw === null || raw === "") continue;
    if (def.kind === "date-range") {
      const v = raw as { from?: string | null; to?: string | null };
      if (v.from) out.set(k(prefix, `f.${def.key}.from`), v.from);
      if (v.to) out.set(k(prefix, `f.${def.key}.to`), v.to);
    } else {
      out.set(k(prefix, `f.${def.key}`), String(raw));
    }
  }
  return out;
}

export function parseState(
  params: URLSearchParams,
  schema: FilterSchema[],
  { prefix = "", defaultPageSize = DEFAULT_PAGE_SIZE }: SerializeOptions = {},
): UrlStateShape {
  const pageRaw = params.get(k(prefix, "page"));
  const sizeRaw = params.get(k(prefix, "size"));
  const sortRaw = params.get(k(prefix, "sort"));

  const pageOneBased = pageRaw ? Math.max(1, parseInt(pageRaw, 10) || 1) : 1;
  const pageSize = sizeRaw
    ? Math.max(1, parseInt(sizeRaw, 10) || defaultPageSize)
    : defaultPageSize;

  let sort: SortState | null = null;
  if (sortRaw) {
    const [id, dir] = sortRaw.split(":");
    if (id) sort = { id, desc: dir === "desc" };
  }

  const filters: FilterState = {};
  for (const def of schema) {
    if (def.kind === "date-range") {
      const from = params.get(k(prefix, `f.${def.key}.from`));
      const to = params.get(k(prefix, `f.${def.key}.to`));
      if (from || to) {
        filters[def.key] = { from: from ?? null, to: to ?? null };
      }
    } else {
      const v = params.get(k(prefix, `f.${def.key}`));
      if (v !== null && v !== "") {
        filters[def.key] = v as FilterValue;
      }
    }
  }

  return {
    pagination: { pageIndex: pageOneBased - 1, pageSize },
    sort,
    filters,
  };
}
