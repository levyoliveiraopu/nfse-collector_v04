/**
 * Cliente das rotas `/companies/{id}/credential` (APP-04 x API-06).
 *
 * - Chama a FastAPI direto via `apiFetch` (cliente autenticado em
 *   memoria pelo `AuthProvider`) — multipart nao passa por Route
 *   Handler local porque o refresh em cookie httpOnly nao e necessario
 *   aqui (access token basta).
 * - Erros da API viram `CredentialApiError` com `status`, `code` e
 *   `message` traduzidos para feedback na UI (senha incorreta, PFX
 *   invalido, PFX excedendo limite, credencial nao configurada, etc).
 */
import { ApiError, apiFetch } from "@/lib/auth/api-client";
import type { AuthSessionPayload } from "@/lib/auth/types";

/** Espelha o `CredentialOut` do backend (API-06 + APP-04 GET). */
export type CredentialStatus = "active" | "expired" | "revoked" | "invalid";

export interface Credential {
  id: string;
  tenant_id: string;
  company_id: string;
  type: "pfx_a1";
  pfx_object_key: string;
  cert_fingerprint: string | null;
  cert_not_before: string | null;
  cert_not_after: string | null;
  status: CredentialStatus;
  /** `null` quando o endpoint nao conseguiu reconferir (ex.: GET). */
  cn_matches_cnpj: boolean | null;
  created_at: string;
  updated_at: string;
}

export type CredentialErrorCode =
  | "not_configured"
  | "invalid_password_or_pfx"
  | "pfx_too_large"
  | "pfx_empty"
  | "pfx_missing_key_or_cert"
  | "storage_failed"
  | "crypto_failed"
  | "forbidden"
  | "unauthorized"
  | "not_found"
  | "network"
  | "unknown";

export class CredentialApiError extends Error {
  status: number;
  code: CredentialErrorCode;
  constructor(status: number, code: CredentialErrorCode, message: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.name = "CredentialApiError";
  }
}

interface ApiCall {
  accessToken: string | null;
  onTokenRefreshed?: (payload: AuthSessionPayload) => void;
}

function detailString(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "detail" in detail) {
    const inner = (detail as { detail?: unknown }).detail;
    if (typeof inner === "string") return inner;
  }
  return "";
}

function mapApiError(err: unknown, fallback: string): CredentialApiError {
  if (err instanceof CredentialApiError) return err;
  if (err instanceof ApiError) {
    const msg = detailString(err.detail).toLowerCase();
    if (err.status === 401) {
      return new CredentialApiError(401, "unauthorized", "sessao expirada");
    }
    if (err.status === 403) {
      return new CredentialApiError(
        403,
        "forbidden",
        "voce nao tem permissao para esta acao",
      );
    }
    if (err.status === 404) {
      if (msg.includes("credencial")) {
        return new CredentialApiError(
          404,
          "not_configured",
          "credencial nao configurada",
        );
      }
      return new CredentialApiError(404, "not_found", "nao encontrado");
    }
    if (err.status === 413) {
      return new CredentialApiError(
        413,
        "pfx_too_large",
        "arquivo PFX excede o limite aceito pelo servidor",
      );
    }
    if (err.status === 502) {
      return new CredentialApiError(
        502,
        "storage_failed",
        "falha ao gravar no storage; tente novamente",
      );
    }
    if (err.status === 400) {
      if (msg.includes("senha") || msg.includes("password") || msg.includes("invalido")) {
        return new CredentialApiError(
          400,
          "invalid_password_or_pfx",
          "senha incorreta ou arquivo PFX invalido",
        );
      }
      if (msg.includes("vazio")) {
        return new CredentialApiError(400, "pfx_empty", "arquivo PFX vazio");
      }
      if (msg.includes("chave privada") || msg.includes("certificado")) {
        return new CredentialApiError(
          400,
          "pfx_missing_key_or_cert",
          "PFX nao contem chave privada ou certificado",
        );
      }
      return new CredentialApiError(
        400,
        "invalid_password_or_pfx",
        detailString(err.detail) || fallback,
      );
    }
    if (err.status === 500) {
      return new CredentialApiError(
        500,
        "crypto_failed",
        "erro interno ao processar a credencial",
      );
    }
    return new CredentialApiError(err.status, "unknown", fallback);
  }
  return new CredentialApiError(0, "network", fallback);
}

async function parseJsonOrThrow<T>(res: Response): Promise<T> {
  const text = await res.text();
  const payload = text ? safeParse(text) : null;
  if (!res.ok) {
    throw new ApiError(res.status, payload ?? text);
  }
  return payload as T;
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/** GET `/companies/{id}/credential`. Devolve `null` quando 404 (nao configurada). */
export async function fetchCredential(
  companyId: string,
  call: ApiCall,
): Promise<Credential | null> {
  try {
    const res = await apiFetch(`/companies/${companyId}/credential`, {
      method: "GET",
      accessToken: call.accessToken,
      onTokenRefreshed: call.onTokenRefreshed,
    });
    if (res.status === 404) return null;
    return await parseJsonOrThrow<Credential>(res);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw mapApiError(err, "falha ao ler credencial");
  }
}

/**
 * POST `/companies/{id}/credential` (multipart: `pfx` + `password`).
 * O `pfx` e enviado como arquivo; a `password` como form field.
 */
export async function uploadCredential(
  companyId: string,
  input: { file: File; password: string },
  call: ApiCall,
): Promise<Credential> {
  const form = new FormData();
  form.append("pfx", input.file);
  form.append("password", input.password);
  try {
    const res = await apiFetch(`/companies/${companyId}/credential`, {
      method: "POST",
      body: form,
      accessToken: call.accessToken,
      onTokenRefreshed: call.onTokenRefreshed,
    });
    return await parseJsonOrThrow<Credential>(res);
  } catch (err) {
    throw mapApiError(err, "falha ao enviar credencial");
  }
}

/** DELETE `/companies/{id}/credential`. Devolve a lista de IDs revogados. */
export async function revokeCredential(
  companyId: string,
  call: ApiCall,
): Promise<{ revoked: string[] }> {
  try {
    const res = await apiFetch(`/companies/${companyId}/credential`, {
      method: "DELETE",
      accessToken: call.accessToken,
      onTokenRefreshed: call.onTokenRefreshed,
    });
    return await parseJsonOrThrow<{ revoked: string[] }>(res);
  } catch (err) {
    throw mapApiError(err, "falha ao revogar credencial");
  }
}

/**
 * Formata fingerprint SHA-256 hex em grupos de 2 separados por `:`,
 * padrao OpenSSL (ex.: `a1:b2:c3:..`). Retorna `""` quando ausente.
 */
export function formatFingerprint(fingerprint: string | null | undefined): string {
  if (!fingerprint) return "";
  const cleaned = fingerprint.replace(/[^0-9a-fA-F]/g, "").toLowerCase();
  if (cleaned.length === 0) return "";
  return cleaned.match(/.{1,2}/g)?.join(":") ?? cleaned;
}

/**
 * Decide a variante de StatusBadge para uma credencial dado `now` (util
 * em testes). `null` = nao configurada.
 *
 * - `status=active` & not_after > now + 30d -> "success"
 * - `status=active` & not_after within 30d  -> "cert_expiring"
 * - `status=active` & not_after <= now      -> "failed" (expirada)
 * - `status=revoked`                         -> "blocked"
 * - `status=invalid`                         -> "cred_invalid"
 * - `status=expired`                         -> "failed"
 * - credencial ausente                       -> "pending"
 */
export type CredentialBadgeVariant =
  | "success"
  | "cert_expiring"
  | "failed"
  | "blocked"
  | "cred_invalid"
  | "pending";

export interface CredentialBadgeDecision {
  variant: CredentialBadgeVariant;
  label: string;
  daysUntilExpiry: number | null;
}

const DAY_MS = 24 * 60 * 60 * 1000;

export function decideCredentialBadge(
  credential: Credential | null,
  now: Date = new Date(),
): CredentialBadgeDecision {
  if (!credential) {
    return { variant: "pending", label: "Nao configurada", daysUntilExpiry: null };
  }
  const status = credential.status;
  let daysUntilExpiry: number | null = null;
  if (credential.cert_not_after) {
    const exp = new Date(credential.cert_not_after).getTime();
    if (!Number.isNaN(exp)) {
      daysUntilExpiry = Math.floor((exp - now.getTime()) / DAY_MS);
    }
  }
  if (status === "revoked") {
    return { variant: "blocked", label: "Revogada", daysUntilExpiry };
  }
  if (status === "invalid") {
    return { variant: "cred_invalid", label: "Invalida", daysUntilExpiry };
  }
  if (status === "expired") {
    return { variant: "failed", label: "Expirada", daysUntilExpiry };
  }
  // active
  if (daysUntilExpiry !== null) {
    if (daysUntilExpiry < 0) {
      return { variant: "failed", label: "Expirada", daysUntilExpiry };
    }
    if (daysUntilExpiry <= 30) {
      return {
        variant: "cert_expiring",
        label: `Expira em ${daysUntilExpiry}d`,
        daysUntilExpiry,
      };
    }
  }
  return { variant: "success", label: "Ativa", daysUntilExpiry };
}
