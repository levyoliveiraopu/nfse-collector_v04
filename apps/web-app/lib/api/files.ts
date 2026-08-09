/**
 * Cliente HTTP de `/files` (consome API-11).
 *
 * - `listFiles` — GET /files paginado com filtros `kind`/`company`/`from`/`to`.
 * - `getFileDownloadUrl` — gera URL pre-assinada 1h (a URL em si nunca e
 *   persistida ou logada; quem chama deve redirecionar/abrir em nova aba).
 *
 * Erros viram `FilesApiError` com `code` canonico para UI. Segue o mesmo
 * padrao de `lib/api/executions.ts`: aceita `ApiCallContext` com
 * `accessToken` + `onTokenRefreshed` e reusa `apiFetch` (retry unico em 401).
 */
import { ApiError, apiFetch } from "@/lib/auth/api-client";
import type { AuthSessionPayload } from "@/lib/auth/types";

export type FileKind = "nfse_xml" | "export" | "pfx" | "report" | "other";

export interface ApiFile {
  id: string;
  tenant_id: string;
  kind: FileKind;
  object_key: string;
  bytes: number;
  checksum_sha256: string;
  source_execution_id: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface FileListResponse {
  items: ApiFile[];
  page: number;
  page_size: number;
  total: number;
}

export interface FileUrlResponse {
  url: string;
  expires_in: number;
  expires_at: string;
}

export type FilesErrorCode =
  | "not_found"
  | "forbidden"
  | "unauthorized"
  | "presign_unavailable"
  | "validation_error"
  | "network"
  | "unknown";

export class FilesApiError extends Error {
  status: number;
  code: FilesErrorCode;

  constructor(status: number, code: FilesErrorCode, message: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.name = "FilesApiError";
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

function mapHttpError(status: number): FilesApiError {
  if (status === 401) return new FilesApiError(status, "unauthorized", "Sessao expirada.");
  if (status === 403) {
    return new FilesApiError(
      status,
      "forbidden",
      "Voce nao tem permissao para acessar arquivos.",
    );
  }
  if (status === 404) {
    return new FilesApiError(status, "not_found", "Arquivo nao encontrado.");
  }
  if (status === 422) {
    return new FilesApiError(
      status,
      "validation_error",
      "Filtros invalidos. Revise periodo/empresa.",
    );
  }
  if (status === 502) {
    return new FilesApiError(
      status,
      "presign_unavailable",
      "Falha ao gerar URL de download. Tente novamente em instantes.",
    );
  }
  return new FilesApiError(status, "unknown", `Erro HTTP ${status}.`);
}

async function readJsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    await parseJsonDetail(res);
    throw mapHttpError(res.status);
  }
  const text = await res.text();
  if (!text) return null as T;
  return JSON.parse(text) as T;
}

function wrapApiError(err: unknown): never {
  if (err instanceof FilesApiError) throw err;
  if (err instanceof ApiError) throw mapHttpError(err.status);
  throw new FilesApiError(
    0,
    "network",
    err instanceof Error ? err.message : "Falha de rede.",
  );
}

export interface ListFilesParams {
  page?: number;
  pageSize?: number;
  page_size?: number;
  kind?: FileKind;
  /** UUID da company (filtra via JOIN em executions no backend). */
  companyId?: string;
  company?: string;
  /** ISO 8601 UTC (`created_at >= from`). */
  from?: string;
  /** ISO 8601 UTC (`created_at < to`). */
  to?: string;
}

const DEFAULT_PAGE_SIZE = 20;

export function buildListQuery(params: ListFilesParams = {}): string {
  const sp = new URLSearchParams();
  sp.set("page", String(params.page ?? 1));
  sp.set(
    "page_size",
    String(params.pageSize ?? params.page_size ?? DEFAULT_PAGE_SIZE),
  );
  if (params.kind) sp.set("kind", params.kind);
  const companyId = params.companyId ?? params.company;
  if (companyId) sp.set("company", companyId);
  if (params.from) sp.set("from", params.from);
  if (params.to) sp.set("to", params.to);
  return sp.toString();
}

export async function listFiles(
  params: ListFilesParams,
  ctx: ApiCallContext,
): Promise<FileListResponse> {
  try {
    const res = await apiFetch(`/files?${buildListQuery(params)}`, {
      method: "GET",
      accessToken: ctx.accessToken,
      onTokenRefreshed: ctx.onTokenRefreshed,
      signal: ctx.signal,
    });
    return readJsonOrThrow<FileListResponse>(res);
  } catch (err) {
    wrapApiError(err);
  }
}

export async function getFileDownloadUrl(
  fileId: string,
  ctx: ApiCallContext,
): Promise<FileUrlResponse> {
  try {
    const res = await apiFetch(`/files/${fileId}/url`, {
      method: "GET",
      accessToken: ctx.accessToken,
      onTokenRefreshed: ctx.onTokenRefreshed,
      signal: ctx.signal,
    });
    return readJsonOrThrow<FileUrlResponse>(res);
  } catch (err) {
    wrapApiError(err);
  }
}

/* --------------------------- Helpers de apresentacao --------------------------- */

export const FILE_KIND_LABEL: Record<FileKind, string> = {
  nfse_xml: "XML (NFS-e)",
  export: "Export",
  pfx: "Certificado",
  report: "Relatorio",
  other: "Outro",
};

/** Distingue os formatos derivados, que compartilham `kind=export` no banco. */
export function getFileKindLabel(
  file: Pick<ApiFile, "kind" | "object_key">,
): string {
  if (file.kind !== "export") return FILE_KIND_LABEL[file.kind];

  const objectKey = file.object_key.toLowerCase();
  if (objectKey.endsWith(".xlsx") || objectKey.endsWith(".xls")) {
    return "Excel NFS-e";
  }
  if (objectKey.endsWith(".zip")) return "XML (ZIP)";
  return FILE_KIND_LABEL.export;
}

/** Kinds expostos no filtro da UI. Oculta `pfx`/`other` (internos). */
export const UI_FILTER_KINDS: readonly FileKind[] = [
  "nfse_xml",
  "export",
  "report",
] as const;

/** Formata bytes em KB/MB/GB com 1 casa decimal. */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  const rounded = i === 0 ? String(Math.round(value)) : value.toFixed(1);
  return `${rounded} ${units[i]}`;
}
