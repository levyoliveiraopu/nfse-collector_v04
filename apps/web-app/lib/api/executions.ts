/**
 * Cliente HTTP de `/executions` (consome API-07 + API-08).
 *
 * Usado pelo dashboard (APP-02) para KPIs agregados e timeline das
 * ultimas execucoes. A agregacao "notas coletadas" e feita client-side
 * somando `items_ok` da primeira pagina (`page_size=100`); quando o
 * total excede 100, o valor e marcado como aproximado no chamador.
 */
import { ApiError, apiFetch } from "@/lib/auth/api-client";

import type { ApiCallContext } from "./companies";

export type ExecutionStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "partial";

export interface Execution {
  id: string;
  tenant_id: string;
  company_id: string;
  trigger: "manual" | "schedule" | "api" | "reprocess";
  status: ExecutionStatus;
  period_start: string;
  period_end: string;
  started_at: string | null;
  finished_at: string | null;
  nsu_from: number | null;
  nsu_to: number | null;
  items_total: number;
  items_ok: number;
  items_fail: number;
  error_summary: string | null;
  triggered_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExecutionListResponse {
  items: Execution[];
  page: number;
  page_size: number;
  total: number;
}

export interface ListExecutionsParams {
  page?: number;
  page_size?: number;
  company_id?: string;
  status?: ExecutionStatus;
  /** ISO 8601 UTC. Filtra `started_at >= from`. */
  from?: string;
  /** ISO 8601 UTC. Filtra `started_at < to`. */
  to?: string;
}

function buildQuery(params: ListExecutionsParams): string {
  const sp = new URLSearchParams();
  if (params.page !== undefined) sp.set("page", String(params.page));
  if (params.page_size !== undefined) sp.set("page_size", String(params.page_size));
  if (params.company_id) sp.set("company_id", params.company_id);
  if (params.status) sp.set("status", params.status);
  if (params.from) sp.set("from", params.from);
  if (params.to) sp.set("to", params.to);
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

export async function listExecutions(
  params: ListExecutionsParams,
  ctx: ApiCallContext,
): Promise<ExecutionListResponse> {
  const qs = buildQuery(params);
  const res = await apiFetch(`/executions${qs ? `?${qs}` : ""}`, {
    method: "GET",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    signal: ctx.signal,
  });
  return readJsonOrThrow<ExecutionListResponse>(res);
}

/**
 * Converte `YYYY-MM-DD` em `YYYY-MM-DDTHH:mm:ss.sssZ` (UTC) apos aplicar
 * `boundary`. Usado para mapear o `PeriodRange` (DS-07) em `from`/`to`
 * da API (que filtra `started_at` como timestamp ISO).
 */
export function periodDateToUtcIso(
  day: string,
  boundary: "start" | "endExclusive",
): string {
  // `boundary === "endExclusive"` avanca 1 dia — a API filtra `started_at < to`.
  const [y, m, d] = day.split("-").map(Number);
  const base = new Date(Date.UTC(y, m - 1, d, 0, 0, 0, 0));
  if (boundary === "endExclusive") {
    base.setUTCDate(base.getUTCDate() + 1);
  }
  return base.toISOString();
}

export const EXECUTION_STATUS_LABEL: Record<ExecutionStatus, string> = {
  queued: "Na fila",
  running: "Em execucao",
  succeeded: "Concluida",
  partial: "Parcial",
  failed: "Falhou",
  cancelled: "Cancelada",
};
