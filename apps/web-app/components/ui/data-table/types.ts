/** Tipos compartilhados pela DataTable (DS-06). */

export type FilterValue =
  | string
  | number
  | null
  | undefined
  | { from?: string | null; to?: string | null };

/** Um filtro aplicavel. */
export interface FilterState {
  [key: string]: FilterValue;
}

export type FilterKind = "text" | "select" | "date-range";

export interface FilterSchemaBase {
  key: string;
  label: string;
  placeholder?: string;
}

export interface TextFilterSchema extends FilterSchemaBase {
  kind: "text";
}

export interface SelectFilterOption {
  value: string;
  label: string;
}

export interface SelectFilterSchema extends FilterSchemaBase {
  kind: "select";
  options: SelectFilterOption[];
}

export interface DateRangeFilterSchema extends FilterSchemaBase {
  kind: "date-range";
}

export type FilterSchema =
  | TextFilterSchema
  | SelectFilterSchema
  | DateRangeFilterSchema;

export interface SortState {
  /** Chave da coluna. */
  id: string;
  /** `true` = desc, `false` = asc. */
  desc: boolean;
}

export interface DataTablePagination {
  pageIndex: number; // zero-based
  pageSize: number;
}

/** Parametros enviados ao fetcher (server-side). */
export interface FetchParams {
  pagination: DataTablePagination;
  sort: SortState | null;
  filters: FilterState;
}

export interface FetchResult<T> {
  rows: T[];
  total: number;
}

export interface SavedFilter {
  id: string;
  name: string;
  filters: FilterState;
  sort: SortState | null;
  createdAt: string; // ISO
}
