/**
 * Cliente HTTP de `/schedules` (consome API-12).
 *
 * Endpoints:
 *   GET    /schedules                (paginado; filtros enabled|company_id)
 *   GET    /schedules/{id}
 *   GET    /schedules/presets
 *   POST   /schedules                (owner|admin|operator)
 *   PATCH  /schedules/{id}           (owner|admin|operator)
 *   DELETE /schedules/{id}           (owner|admin)
 *
 * RBAC: leitura liberada para todos os papeis (viewer inclusive), gravacao
 * segue a matriz em `docs/architecture/rbac-matrix.md` — o backend retorna
 * 403 para papeis insuficientes e a UI desabilita controles.
 */
import { ApiError, apiFetch } from "@/lib/auth/api-client";
import type { AuthSessionPayload } from "@/lib/auth/types";

export type Schedule = {
  id: string;
  tenant_id: string;
  /** Null = agenda valida para o tenant inteiro. */
  company_id: string | null;
  cron_expr: string;
  /** Nome IANA (ex.: "America/Sao_Paulo"). */
  timezone: string;
  enabled: boolean;
  /** ISO 8601 UTC ou null. */
  last_run_at: string | null;
  /** ISO 8601 UTC ou null (null enquanto enabled=false). */
  next_run_at: string | null;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ScheduleListResponse = {
  items: Schedule[];
  page: number;
  page_size: number;
  total: number;
};

export type SchedulePreset = {
  id: string;
  label: string;
  cron_expr: string;
  description: string;
};

export type SchedulePresetListResponse = {
  items: SchedulePreset[];
};

export type ScheduleCreatePayload = {
  cron_expr: string;
  timezone: string;
  company_id?: string | null;
  enabled?: boolean;
};

/** Partial no PATCH — `extra=forbid` no backend rejeita campos read-only. */
export type ScheduleUpdatePayload = Partial<{
  cron_expr: string;
  timezone: string;
  company_id: string | null;
  enabled: boolean;
}>;

export type ApiCallContext = {
  accessToken: string | null;
  onTokenRefreshed?: (payload: AuthSessionPayload) => void;
  signal?: AbortSignal;
};

export type ListSchedulesParams = {
  page?: number;
  pageSize?: number;
  enabled?: boolean | null;
  companyId?: string | null;
};

function buildListQuery(params: ListSchedulesParams): string {
  const sp = new URLSearchParams();
  sp.set("page", String(params.page ?? 1));
  sp.set("page_size", String(params.pageSize ?? 50));
  if (typeof params.enabled === "boolean") {
    sp.set("enabled", params.enabled ? "true" : "false");
  }
  if (params.companyId) {
    sp.set("company_id", params.companyId);
  }
  return sp.toString();
}

async function readJsonOrThrow<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!res.ok) {
    let detail: unknown = text;
    try {
      detail = text ? JSON.parse(text) : null;
    } catch {
      // string crua
    }
    throw new ApiError(res.status, detail);
  }
  if (!text) return null as T;
  return JSON.parse(text) as T;
}

export async function listSchedules(
  params: ListSchedulesParams,
  ctx: ApiCallContext,
): Promise<ScheduleListResponse> {
  const qs = buildListQuery(params);
  const res = await apiFetch(`/schedules${qs ? `?${qs}` : ""}`, {
    method: "GET",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    signal: ctx.signal,
  });
  return readJsonOrThrow<ScheduleListResponse>(res);
}

export async function getSchedule(
  id: string,
  ctx: ApiCallContext,
): Promise<Schedule> {
  const res = await apiFetch(`/schedules/${encodeURIComponent(id)}`, {
    method: "GET",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    signal: ctx.signal,
  });
  return readJsonOrThrow<Schedule>(res);
}

export async function listSchedulePresets(
  ctx: ApiCallContext,
): Promise<SchedulePreset[]> {
  const res = await apiFetch("/schedules/presets", {
    method: "GET",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    signal: ctx.signal,
  });
  const data = await readJsonOrThrow<SchedulePresetListResponse>(res);
  return data.items;
}

export async function createSchedule(
  body: ScheduleCreatePayload,
  ctx: ApiCallContext,
): Promise<Schedule> {
  const res = await apiFetch("/schedules", {
    method: "POST",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
    signal: ctx.signal,
  });
  return readJsonOrThrow<Schedule>(res);
}

export async function updateSchedule(
  id: string,
  body: ScheduleUpdatePayload,
  ctx: ApiCallContext,
): Promise<Schedule> {
  const res = await apiFetch(`/schedules/${encodeURIComponent(id)}`, {
    method: "PATCH",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
    signal: ctx.signal,
  });
  return readJsonOrThrow<Schedule>(res);
}

export async function toggleSchedule(
  id: string,
  enabled: boolean,
  ctx: ApiCallContext,
): Promise<Schedule> {
  return updateSchedule(id, { enabled }, ctx);
}

export async function deleteSchedule(
  id: string,
  ctx: ApiCallContext,
): Promise<void> {
  const res = await apiFetch(`/schedules/${encodeURIComponent(id)}`, {
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
      // string crua
    }
    throw new ApiError(res.status, detail);
  }
}

/**
 * Extrai a mensagem de erro curta do formato FastAPI. Prefere `detail`
 * como string; fallback para JSON.stringify truncado.
 */
export function extractErrorDetail(err: unknown): string | null {
  if (!(err instanceof ApiError)) return null;
  const d = err.detail;
  if (typeof d === "string") return d;
  if (d && typeof d === "object") {
    const detail = (d as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return null;
}
