/**
 * Cliente HTTP de `/occurrences` (consome API-09).
 *
 * Espelha o contrato de `apps/api/api/occurrences/schemas.py`:
 * - `OccurrenceOut`               -> `Occurrence`
 * - `OccurrenceListOut`           -> `OccurrenceListResponse`
 * - `OccurrenceResolveIn`         -> `ResolvePayload`
 * - `OccurrenceAssignIn`          -> `AssignPayload`
 *
 * Convencoes iguais a `companies.ts` (APP-03): `apiFetch` faz refresh de
 * access token em 401; erros 4xx/5xx viram `ApiError`.
 *
 * `listOccurrences` aceita dois shapes de input:
 * 1. `FetchParams` do `<DataTable>` — usado por `app/ocorrencias/` (APP-06).
 *    Retorna `FetchResult<Occurrence>` (`{rows, total}`).
 * 2. `ListOccurrencesParams` com `status`/`page`/`page_size` — usado pelo
 *    dashboard (APP-02, KPI "ocorrencias abertas"). Retorna o mesmo
 *    `FetchResult<Occurrence>` para simplicidade; o consumidor so olha
 *    `.total` nesse caminho.
 */
import { ApiError, apiFetch } from "@/lib/auth/api-client";
import type { AuthSessionPayload } from "@/lib/auth/types";
import type { FetchParams, FetchResult } from "@/components/ui/data-table";

export type OccurrenceSeverity = "info" | "warning" | "error" | "critical";
export type OccurrenceStatus =
  | "open"
  | "ack"
  | "snoozed"
  | "resolved"
  | "ignored";

export interface Occurrence {
  id: string;
  tenant_id: string;
  company_id: string;
  execution_id: string | null;
  severity: OccurrenceSeverity;
  code: string;
  title: string;
  detail: string | null;
  status: OccurrenceStatus;
  assignee_user_id: string | null;
  first_seen_at: string;
  last_seen_at: string;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OccurrenceListResponse {
  items: Occurrence[];
  page: number;
  page_size: number;
  total: number;
}

export interface ResolvePayload {
  note: string;
}

export interface AssignPayload {
  assignee_user_id: string;
}

export interface ApiCallContext {
  accessToken: string | null;
  onTokenRefreshed?: (payload: AuthSessionPayload) => void;
  signal?: AbortSignal;
}

export interface ListOccurrencesParams {
  page?: number;
  page_size?: number;
  pageSize?: number;
  status?: OccurrenceStatus;
  severity?: OccurrenceSeverity;
  company_id?: string;
  companyId?: string;
}

/**
 * Narrow-typed helper: `p` e um `FetchParams` (tem `pagination`, `sort`,
 * `filters`).
 */
function isFetchParams(p: unknown): p is FetchParams {
  return (
    typeof p === "object" &&
    p !== null &&
    "pagination" in p &&
    "filters" in p
  );
}

/** Mapeia parametros do `<DataTable>` para a querystring de `GET /occurrences`. */
export function buildListQuery(params: FetchParams): string {
  const sp = new URLSearchParams();
  sp.set("page", String(params.pagination.pageIndex + 1));
  sp.set("page_size", String(params.pagination.pageSize));
  const status = params.filters.status;
  if (typeof status === "string" && status.length > 0) {
    sp.set("status", status);
  }
  const severity = params.filters.severity;
  if (typeof severity === "string" && severity.length > 0) {
    sp.set("severity", severity);
  }
  const companyId = params.filters.company_id;
  if (typeof companyId === "string" && companyId.trim().length > 0) {
    sp.set("company_id", companyId.trim());
  }
  return sp.toString();
}

function buildListParamsQuery(params: ListOccurrencesParams): string {
  const sp = new URLSearchParams();
  if (params.page !== undefined) sp.set("page", String(params.page));
  const pageSize = params.pageSize ?? params.page_size;
  if (pageSize !== undefined) sp.set("page_size", String(pageSize));
  if (params.status) sp.set("status", params.status);
  if (params.severity) sp.set("severity", params.severity);
  const companyId = params.companyId ?? params.company_id;
  if (companyId) sp.set("company_id", companyId);
  return sp.toString();
}

async function readJsonOrThrow<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!res.ok) {
    let detail: unknown = text;
    try {
      detail = text ? JSON.parse(text) : null;
    } catch {
      // mantem string crua
    }
    throw new ApiError(res.status, detail);
  }
  if (!text) return null as T;
  return JSON.parse(text) as T;
}

/**
 * GET `/occurrences`. Ambos os shapes de input (FetchParams do
 * `<DataTable>` ou `ListOccurrencesParams` com `status`/`page_size`)
 * sao aceitos; o retorno canonico e `FetchResult<Occurrence>`.
 */
export async function listOccurrences(
  params: FetchParams | ListOccurrencesParams,
  ctx: ApiCallContext,
): Promise<FetchResult<Occurrence>> {
  const qs = isFetchParams(params)
    ? buildListQuery(params)
    : buildListParamsQuery(params);
  const res = await apiFetch(`/occurrences${qs ? `?${qs}` : ""}`, {
    method: "GET",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    signal: ctx.signal,
  });
  const data = await readJsonOrThrow<OccurrenceListResponse>(res);
  return { rows: data.items, total: data.total };
}

export async function getOccurrence(
  id: string,
  ctx: ApiCallContext,
): Promise<Occurrence> {
  const res = await apiFetch(`/occurrences/${id}`, {
    method: "GET",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    signal: ctx.signal,
  });
  return readJsonOrThrow<Occurrence>(res);
}

export async function acknowledgeOccurrence(
  id: string,
  ctx: ApiCallContext,
): Promise<Occurrence> {
  const res = await apiFetch(`/occurrences/${id}/acknowledge`, {
    method: "POST",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    signal: ctx.signal,
  });
  return readJsonOrThrow<Occurrence>(res);
}

export async function resolveOccurrence(
  id: string,
  body: ResolvePayload,
  ctx: ApiCallContext,
): Promise<Occurrence> {
  const res = await apiFetch(`/occurrences/${id}/resolve`, {
    method: "POST",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
    signal: ctx.signal,
  });
  return readJsonOrThrow<Occurrence>(res);
}

export async function assignOccurrence(
  id: string,
  body: AssignPayload,
  ctx: ApiCallContext,
): Promise<Occurrence> {
  const res = await apiFetch(`/occurrences/${id}/assign`, {
    method: "POST",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
    signal: ctx.signal,
  });
  return readJsonOrThrow<Occurrence>(res);
}

/**
 * Helpers de apresentacao.
 */

export const OCCURRENCE_STATUS_LABEL: Record<OccurrenceStatus, string> = {
  open: "Aberta",
  ack: "Reconhecida",
  snoozed: "Adiada",
  resolved: "Resolvida",
  ignored: "Ignorada",
};

export const OCCURRENCE_SEVERITY_LABEL: Record<OccurrenceSeverity, string> = {
  info: "Info",
  warning: "Aviso",
  error: "Erro",
  critical: "Critico",
};

/** Status que nao aceitam mais transicao de acknowledge/resolve. */
export function isTerminal(status: OccurrenceStatus): boolean {
  return status === "resolved" || status === "ignored";
}
