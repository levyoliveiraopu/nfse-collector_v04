/**
 * Cliente HTTP de `/occurrences` (consome API-09).
 *
 * Usado pelo dashboard (APP-02) para a contagem de ocorrencias
 * abertas. Para esse KPI basta o `total` do envelope — por isso
 * consultamos com `page_size=1`.
 */
import { ApiError, apiFetch } from "@/lib/auth/api-client";

import type { ApiCallContext } from "./companies";

export type OccurrenceStatus = "open" | "ack" | "snoozed" | "resolved" | "ignored";
export type OccurrenceSeverity = "info" | "warning" | "error" | "critical";

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

export interface ListOccurrencesParams {
  page?: number;
  page_size?: number;
  status?: OccurrenceStatus;
  severity?: OccurrenceSeverity;
  company_id?: string;
}

function buildQuery(params: ListOccurrencesParams): string {
  const sp = new URLSearchParams();
  if (params.page !== undefined) sp.set("page", String(params.page));
  if (params.page_size !== undefined) sp.set("page_size", String(params.page_size));
  if (params.status) sp.set("status", params.status);
  if (params.severity) sp.set("severity", params.severity);
  if (params.company_id) sp.set("company_id", params.company_id);
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

export async function listOccurrences(
  params: ListOccurrencesParams,
  ctx: ApiCallContext,
): Promise<OccurrenceListResponse> {
  const qs = buildQuery(params);
  const res = await apiFetch(`/occurrences${qs ? `?${qs}` : ""}`, {
    method: "GET",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    signal: ctx.signal,
  });
  return readJsonOrThrow<OccurrenceListResponse>(res);
}
