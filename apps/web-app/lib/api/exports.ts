/**
 * Cliente HTTP de `/exports` (consome API-15 — export ZIP assincrono).
 *
 * - `createExport` — POST /exports (owner|admin|operator). Retorna
 *   `{export_id, status, job_id, enqueue_error}`. Em falha pos-INSERT,
 *   o backend marca `status='failed'` e `enqueue_error='enqueue_failed'`.
 * - `getExport` — GET /exports/{id} (todos os papeis). Quando `status`
 *   esta `ready`, inclui `download_url` + `expires_in` (URL pre-assinada
 *   1h).
 *
 * Erros viram `ExportsApiError` com `code` canonico.
 */
import { ApiError, apiFetch } from "@/lib/auth/api-client";
import type { AuthSessionPayload } from "@/lib/auth/types";

export type ExportKind = "zip_xml";

export type ExportStatus = "queued" | "running" | "ready" | "failed" | "empty";

export const EXPORT_TERMINAL_STATUSES: ReadonlySet<ExportStatus> = new Set([
  "ready",
  "failed",
  "empty",
]);

export interface ExportRecord {
  id: string;
  tenant_id: string;
  company_id: string;
  requested_by_user_id: string | null;
  kind: ExportKind;
  period_start: string;
  period_end: string;
  status: ExportStatus;
  file_id: string | null;
  items_count: number;
  total_bytes: number;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
  download_url: string | null;
  expires_in: number | null;
}

export interface CreateExportPayload {
  company_id: string;
  period_start: string;
  period_end: string;
  kind?: ExportKind;
}

export interface CreateExportResponse {
  export_id: string;
  status: ExportStatus;
  job_id: string | null;
  enqueue_error: string | null;
}

export type ExportsErrorCode =
  | "company_not_found"
  | "queue_unavailable"
  | "validation_error"
  | "forbidden"
  | "unauthorized"
  | "not_found"
  | "presign_unavailable"
  | "network"
  | "unknown";

export class ExportsApiError extends Error {
  status: number;
  code: ExportsErrorCode;

  constructor(status: number, code: ExportsErrorCode, message: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.name = "ExportsApiError";
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

function extractBackendError(detail: unknown): string | null {
  if (detail && typeof detail === "object" && "detail" in detail) {
    const inner = (detail as { detail?: unknown }).detail;
    if (inner && typeof inner === "object") {
      const raw = (inner as Record<string, unknown>)["error"];
      if (typeof raw === "string") return raw;
    }
  }
  return null;
}

function mapHttpError(status: number, detail: unknown): ExportsApiError {
  if (status === 401) {
    return new ExportsApiError(status, "unauthorized", "Sessao expirada.");
  }
  if (status === 403) {
    return new ExportsApiError(
      status,
      "forbidden",
      "Voce nao tem permissao para gerar exports.",
    );
  }
  if (status === 404) {
    return new ExportsApiError(status, "not_found", "Export nao encontrado.");
  }
  if (status === 422) {
    const backendError = extractBackendError(detail);
    if (backendError === "company_not_found") {
      return new ExportsApiError(
        status,
        "company_not_found",
        "Empresa nao encontrada ou sem acesso.",
      );
    }
    return new ExportsApiError(
      status,
      "validation_error",
      "Dados invalidos. Revise empresa e periodo.",
    );
  }
  if (status === 502) {
    return new ExportsApiError(
      status,
      "queue_unavailable",
      "Fila de jobs indisponivel. Tente novamente em instantes.",
    );
  }
  return new ExportsApiError(status, "unknown", `Erro HTTP ${status}.`);
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
  if (err instanceof ExportsApiError) throw err;
  if (err instanceof ApiError) throw mapHttpError(err.status, err.detail);
  throw new ExportsApiError(
    0,
    "network",
    err instanceof Error ? err.message : "Falha de rede.",
  );
}

export async function createExport(
  payload: CreateExportPayload,
  ctx: ApiCallContext,
): Promise<CreateExportResponse> {
  try {
    const res = await apiFetch(`/exports`, {
      method: "POST",
      accessToken: ctx.accessToken,
      onTokenRefreshed: ctx.onTokenRefreshed,
      body: JSON.stringify(payload),
      headers: { "Content-Type": "application/json" },
      signal: ctx.signal,
    });
    return readJsonOrThrow<CreateExportResponse>(res);
  } catch (err) {
    wrapApiError(err);
  }
}

export async function getExport(
  exportId: string,
  ctx: ApiCallContext,
): Promise<ExportRecord> {
  try {
    const res = await apiFetch(`/exports/${exportId}`, {
      method: "GET",
      accessToken: ctx.accessToken,
      onTokenRefreshed: ctx.onTokenRefreshed,
      signal: ctx.signal,
    });
    return readJsonOrThrow<ExportRecord>(res);
  } catch (err) {
    wrapApiError(err);
  }
}

export function isTerminalExportStatus(status: ExportStatus): boolean {
  return EXPORT_TERMINAL_STATUSES.has(status);
}

export const EXPORT_STATUS_LABEL: Record<ExportStatus, string> = {
  queued: "Na fila",
  running: "Processando",
  ready: "Pronto",
  failed: "Falhou",
  empty: "Sem dados",
};
