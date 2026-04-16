/**
 * Cliente HTTP de `/companies` (consome API-05).
 *
 * Convencoes:
 * - Todas as funcoes recebem `ApiCallContext` com o `accessToken` em
 *   memoria (vindo do `useAuth()`) e um callback opcional de refresh,
 *   reaproveitando `apiFetch` (que ja faz retry uma vez em 401).
 * - Erros HTTP viram `ApiError` com `status` e `detail`. O detalhe
 *   segue o formato FastAPI (`{ detail: string | object }`).
 * - Nao depende de Next runtime — testavel no jsdom passando `fetch`
 *   global mockado.
 */
import { ApiError, apiFetch } from "@/lib/auth/api-client";
import type { AuthSessionPayload } from "@/lib/auth/types";
import type { FetchParams, FetchResult } from "@/components/ui/data-table";

export type CompanyStatus = "active" | "paused" | "disabled";

export interface Company {
  id: string;
  tenant_id: string;
  cnpj: string;
  razao_social: string;
  nome_fantasia: string | null;
  municipio_ibge: string;
  uf: string;
  status: CompanyStatus;
  last_nsu: number | null;
  last_success_at: string | null;
  portal_provider: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CompanyListResponse {
  items: Company[];
  page: number;
  page_size: number;
  total: number;
}

export interface CompanyCreatePayload {
  cnpj: string;
  razao_social: string;
  nome_fantasia?: string | null;
  municipio_ibge: string;
  uf: string;
  status?: CompanyStatus;
  portal_provider?: string | null;
  notes?: string | null;
}

export type CompanyUpdatePayload = Partial<
  Omit<CompanyCreatePayload, "cnpj">
>;

export interface ApiCallContext {
  accessToken: string | null;
  onTokenRefreshed?: (payload: AuthSessionPayload) => void;
  signal?: AbortSignal;
}

/** Mapeia parametros do `<DataTable>` para a querystring de `GET /companies`. */
export function buildListQuery(params: FetchParams): string {
  const sp = new URLSearchParams();
  // API-05 usa page 1-based; DataTable usa pageIndex 0-based.
  sp.set("page", String(params.pagination.pageIndex + 1));
  sp.set("page_size", String(params.pagination.pageSize));
  const status = params.filters.status;
  if (typeof status === "string" && status.length > 0) {
    sp.set("status", status);
  }
  const uf = params.filters.uf;
  if (typeof uf === "string" && uf.trim().length > 0) {
    sp.set("uf", uf.trim().toUpperCase());
  }
  // sort: API-05 ainda nao expoe `?sort=`; quando expuser, mapear aqui.
  // last_success_at: API-05 ainda nao filtra por periodo; coluna fica
  // apenas exibicional ate ticket de extensao.
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

/** Lista paginada de companies (consumida pelo `<DataTable>`). */
export async function listCompanies(
  params: FetchParams,
  ctx: ApiCallContext,
): Promise<FetchResult<Company>> {
  const qs = buildListQuery(params);
  const res = await apiFetch(`/companies${qs ? `?${qs}` : ""}`, {
    method: "GET",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    signal: ctx.signal,
  });
  const data = await readJsonOrThrow<CompanyListResponse>(res);
  return { rows: data.items, total: data.total };
}

export async function getCompany(
  id: string,
  ctx: ApiCallContext,
): Promise<Company> {
  const res = await apiFetch(`/companies/${id}`, {
    method: "GET",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    signal: ctx.signal,
  });
  return readJsonOrThrow<Company>(res);
}

export async function createCompany(
  body: CompanyCreatePayload,
  ctx: ApiCallContext,
): Promise<Company> {
  const res = await apiFetch(`/companies`, {
    method: "POST",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
    signal: ctx.signal,
  });
  return readJsonOrThrow<Company>(res);
}

export async function updateCompany(
  id: string,
  body: CompanyUpdatePayload,
  ctx: ApiCallContext,
): Promise<Company> {
  const res = await apiFetch(`/companies/${id}`, {
    method: "PATCH",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
    signal: ctx.signal,
  });
  return readJsonOrThrow<Company>(res);
}

export async function deleteCompany(
  id: string,
  ctx: ApiCallContext,
): Promise<void> {
  const res = await apiFetch(`/companies/${id}`, {
    method: "DELETE",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    signal: ctx.signal,
  });
  if (!res.ok) {
    const text = await res.text();
    let detail: unknown = text;
    try {
      detail = text ? JSON.parse(text) : null;
    } catch {
      // mantem string crua
    }
    throw new ApiError(res.status, detail);
  }
}

/**
 * Helpers de apresentacao reaproveitados pelos componentes.
 */

export function formatCnpj(raw: string): string {
  const d = raw.replace(/\D/g, "");
  if (d.length !== 14) return raw;
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12, 14)}`;
}

export const COMPANY_STATUS_LABEL: Record<CompanyStatus, string> = {
  active: "Ativa",
  paused: "Pausada",
  disabled: "Desativada",
};
