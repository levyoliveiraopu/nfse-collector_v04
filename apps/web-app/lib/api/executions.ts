/**
 * Cliente HTTP dos endpoints de `/executions` (consome API-07 + API-08).
 *
 * - `listExecutions` / `getExecution` / `listExecutionItems` sao leituras
 *   paginadas; RBAC libera para todos os papeis (matriz).
 * - `createExecutions` enfileira N jobs no RQ (owner|admin|operator). A
 *   resposta traz `job_id=null` + `enqueue_error` quando uma linha falhou
 *   no enqueue pos-INSERT — tratada como erro parcial no caller.
 * - Erros HTTP viram `ExecutionsApiError` com `code` canonico pra UI:
 *   `companies_not_found` / `credential_missing_or_expired` vem do 422
 *   estruturado do backend; `queue_unavailable` do 502; `forbidden` do
 *   403; `not_found` do 404.
 *
 * Convencao de parametros: o input aceita **camelCase** (pageSize,
 * companyId) OU **snake_case** (page_size, company_id). Isso preserva
 * os 2 consumidores pre-existentes: APP-02 (dashboard) usa snake_case
 * por pegar `...window` ja no shape da API; APP-05 (execucoes list
 * etc.) usa camelCase. A querystring final e sempre snake_case,
 * alinhada com a API FastAPI.
 */
import { ApiError, apiFetch } from "@/lib/auth/api-client";
import type { AuthSessionPayload } from "@/lib/auth/types";

export type ExecutionTrigger = "manual" | "schedule" | "api" | "reprocess";

export type ExecutionStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "partial";

export type ExecutionItemStatus = "ok" | "failed" | "skipped" | "pending";

export const EXECUTION_TERMINAL_STATUSES: ReadonlySet<ExecutionStatus> = new Set(
  ["succeeded", "failed", "cancelled", "partial"],
);

export interface Execution {
  id: string;
  tenant_id: string;
  company_id: string;
  trigger: ExecutionTrigger;
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

export interface ExecutionItem {
  id: string;
  tenant_id: string;
  execution_id: string;
  nsu: number | null;
  chave_nfse: string | null;
  cnpj_emitente: string | null;
  data_emissao: string | null;
  valor: string | null;
  xml_object_key: string | null;
  status: ExecutionItemStatus;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExecutionItemListResponse {
  items: ExecutionItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface CreateExecutionsPayload {
  company_ids: string[];
  period_start: string;
  period_end: string;
  dry_run?: boolean;
  trigger?: ExecutionTrigger;
}

export interface CreatedExecution {
  execution_id: string;
  company_id: string;
  status: ExecutionStatus;
  job_id: string | null;
  enqueue_error: string | null;
}

export interface CreateExecutionsResponse {
  created: CreatedExecution[];
}

export type ExecutionsErrorCode =
  | "companies_not_found"
  | "credential_missing_or_expired"
  | "queue_unavailable"
  | "validation_error"
  | "forbidden"
  | "unauthorized"
  | "not_found"
  | "network"
  | "unknown";

export class ExecutionsApiError extends Error {
  status: number;
  code: ExecutionsErrorCode;
  extra: { companyIds: string[] };

  constructor(
    status: number,
    code: ExecutionsErrorCode,
    message: string,
    extra: { companyIds?: string[] } = {},
  ) {
    super(message);
    this.status = status;
    this.code = code;
    this.extra = { companyIds: extra.companyIds ?? [] };
    this.name = "ExecutionsApiError";
  }
}

export interface ApiCallContext {
  accessToken: string | null;
  onTokenRefreshed?: (payload: AuthSessionPayload) => void;
  signal?: AbortSignal;
}

async function parseJsonDetail(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function extractBackendDetail(detail: unknown): {
  error: string | null;
  companyIds: string[];
} {
  if (detail && typeof detail === "object" && "detail" in detail) {
    const inner = (detail as { detail?: unknown }).detail;
    if (inner && typeof inner === "object") {
      const obj = inner as Record<string, unknown>;
      const rawError = obj["error"];
      const error = typeof rawError === "string" ? rawError : null;
      const list =
        (obj["company_ids"] as unknown) ?? (obj["missing"] as unknown) ?? [];
      const companyIds = Array.isArray(list)
        ? list.filter((x): x is string => typeof x === "string")
        : [];
      return { error, companyIds };
    }
  }
  return { error: null, companyIds: [] };
}

function mapHttpError(status: number, detail: unknown): ExecutionsApiError {
  if (status === 401) {
    return new ExecutionsApiError(status, "unauthorized", "Sessao expirada.");
  }
  if (status === 403) {
    return new ExecutionsApiError(
      status,
      "forbidden",
      "Voce nao tem permissao para esta acao.",
    );
  }
  if (status === 404) {
    return new ExecutionsApiError(status, "not_found", "Recurso nao encontrado.");
  }
  if (status === 502) {
    return new ExecutionsApiError(
      status,
      "queue_unavailable",
      "Fila de jobs indisponivel. Tente novamente em instantes.",
    );
  }
  if (status === 422) {
    const { error, companyIds } = extractBackendDetail(detail);
    if (error === "companies_not_found") {
      return new ExecutionsApiError(
        status,
        "companies_not_found",
        "Uma ou mais empresas nao foram encontradas.",
        { companyIds },
      );
    }
    if (error === "credential_missing_or_expired") {
      return new ExecutionsApiError(
        status,
        "credential_missing_or_expired",
        "Empresas sem credencial ativa ou com certificado vencido.",
        { companyIds },
      );
    }
    return new ExecutionsApiError(
      status,
      "validation_error",
      "Dados invalidos. Revise o formulario.",
    );
  }
  return new ExecutionsApiError(status, "unknown", `Erro HTTP ${status}.`);
}

async function readJsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await parseJsonDetail(res);
    throw mapHttpError(res.status, detail);
  }
  const text = await res.text();
  if (!text) return null as T;
  return JSON.parse(text) as T;
}

function wrapApiError(err: unknown): never {
  if (err instanceof ExecutionsApiError) throw err;
  if (err instanceof ApiError) {
    throw mapHttpError(err.status, err.detail);
  }
  throw new ExecutionsApiError(
    0,
    "network",
    err instanceof Error ? err.message : "Falha de rede.",
  );
}

/**
 * Parametros de `listExecutions`. Aceita os dois estilos de nomeacao
 * (camelCase vindo de APP-05 e snake_case vindo de APP-02) — o
 * serializador normaliza para snake_case no URL.
 */
export interface ListExecutionsParams {
  page?: number;
  pageSize?: number;
  page_size?: number;
  companyId?: string;
  company_id?: string;
  status?: ExecutionStatus;
  /** ISO 8601 UTC (started_at >=). */
  from?: string;
  /** ISO 8601 UTC (started_at <). */
  to?: string;
}

const DEFAULT_LIST_PAGE_SIZE = 20;

export function buildListQuery(params: ListExecutionsParams = {}): string {
  const sp = new URLSearchParams();
  const page = params.page ?? 1;
  const pageSize = params.pageSize ?? params.page_size ?? DEFAULT_LIST_PAGE_SIZE;
  sp.set("page", String(page));
  sp.set("page_size", String(pageSize));
  const companyId = params.companyId ?? params.company_id;
  if (companyId) sp.set("company_id", companyId);
  if (params.status) sp.set("status", params.status);
  if (params.from) sp.set("from", params.from);
  if (params.to) sp.set("to", params.to);
  return sp.toString();
}

export async function listExecutions(
  params: ListExecutionsParams,
  ctx: ApiCallContext,
): Promise<ExecutionListResponse> {
  try {
    const res = await apiFetch(`/executions?${buildListQuery(params)}`, {
      method: "GET",
      accessToken: ctx.accessToken,
      onTokenRefreshed: ctx.onTokenRefreshed,
      signal: ctx.signal,
    });
    return readJsonOrThrow<ExecutionListResponse>(res);
  } catch (err) {
    wrapApiError(err);
  }
}

export async function getExecution(
  id: string,
  ctx: ApiCallContext,
): Promise<Execution> {
  try {
    const res = await apiFetch(`/executions/${id}`, {
      method: "GET",
      accessToken: ctx.accessToken,
      onTokenRefreshed: ctx.onTokenRefreshed,
      signal: ctx.signal,
    });
    return readJsonOrThrow<Execution>(res);
  } catch (err) {
    wrapApiError(err);
  }
}

export interface ListItemsParams {
  page?: number;
  pageSize?: number;
  page_size?: number;
  status?: ExecutionItemStatus;
  nsu?: number;
}

const DEFAULT_ITEMS_PAGE_SIZE = 50;

export function buildItemsQuery(params: ListItemsParams = {}): string {
  const sp = new URLSearchParams();
  sp.set("page", String(params.page ?? 1));
  sp.set(
    "page_size",
    String(params.pageSize ?? params.page_size ?? DEFAULT_ITEMS_PAGE_SIZE),
  );
  if (params.status) sp.set("status", params.status);
  if (typeof params.nsu === "number") sp.set("nsu", String(params.nsu));
  return sp.toString();
}

export async function listExecutionItems(
  executionId: string,
  params: ListItemsParams,
  ctx: ApiCallContext,
): Promise<ExecutionItemListResponse> {
  try {
    const res = await apiFetch(
      `/executions/${executionId}/items?${buildItemsQuery(params)}`,
      {
        method: "GET",
        accessToken: ctx.accessToken,
        onTokenRefreshed: ctx.onTokenRefreshed,
        signal: ctx.signal,
      },
    );
    return readJsonOrThrow<ExecutionItemListResponse>(res);
  } catch (err) {
    wrapApiError(err);
  }
}

export async function createExecutions(
  payload: CreateExecutionsPayload,
  ctx: ApiCallContext,
): Promise<CreateExecutionsResponse> {
  try {
    const res = await apiFetch(`/executions`, {
      method: "POST",
      accessToken: ctx.accessToken,
      onTokenRefreshed: ctx.onTokenRefreshed,
      body: JSON.stringify(payload),
      headers: { "Content-Type": "application/json" },
      signal: ctx.signal,
    });
    return readJsonOrThrow<CreateExecutionsResponse>(res);
  } catch (err) {
    wrapApiError(err);
  }
}

/* --------------------------- Helpers de apresentacao --------------------------- */

export type ExecutionBadgeVariant =
  | "pending"
  | "processing"
  | "success"
  | "failed"
  | "blocked"
  | "warning";

export function decideExecutionBadge(
  status: ExecutionStatus,
): ExecutionBadgeVariant {
  switch (status) {
    case "queued":
      return "pending";
    case "running":
      return "processing";
    case "succeeded":
      return "success";
    case "failed":
      return "failed";
    case "cancelled":
      return "blocked";
    case "partial":
      return "warning";
  }
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
  failed: "Falhou",
  cancelled: "Cancelada",
  partial: "Parcial",
};

export const EXECUTION_ITEM_STATUS_LABEL: Record<ExecutionItemStatus, string> = {
  ok: "OK",
  failed: "Falhou",
  skipped: "Ignorado",
  pending: "Pendente",
};

export function computeProgress(
  execution: Pick<Execution, "items_total" | "items_ok" | "items_fail" | "status">,
): { processed: number; total: number; percent: number } {
  const processed = execution.items_ok + execution.items_fail;
  const total = Math.max(execution.items_total, processed);
  const percent =
    total === 0 ? 0 : Math.min(100, Math.round((processed / total) * 100));
  return { processed, total, percent };
}

export function isTerminalStatus(status: ExecutionStatus): boolean {
  return EXECUTION_TERMINAL_STATUSES.has(status);
}
