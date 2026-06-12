/**
 * Cliente HTTP minimalista para chamadas autenticadas ao backend FastAPI.
 *
 * Regras:
 * - Endpoints publicos de auth (/login, /signup, /refresh, /logout) passam
 *   pelos Route Handlers locais (`/api/auth/*`), que gravam/leem o refresh
 *   em cookie httpOnly e devolvem apenas o access token.
 * - Endpoints protegidos sao chamados direto na API, injetando o header
 *   Authorization com o access token em memoria. Em 401, tentamos refresh
 *   automatico uma unica vez antes de falhar.
 */
import type { AuthSessionPayload } from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? `API error ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

type RequestOptions = RequestInit & {
  /** Access token atual (obtido do AuthProvider). */
  accessToken?: string | null;
  /** Callback chamado quando o access expira e obtemos um novo via refresh. */
  onTokenRefreshed?: (payload: AuthSessionPayload) => void;
  /** Impede recursao infinita ao retentar pos-refresh. */
  _retryAfterRefresh?: boolean;
};

async function parseJsonSafe(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/**
 * Faz fetch direto no backend com Authorization injetado. Se receber 401 e
 * `onTokenRefreshed` for informado, tenta refresh via Route Handler local
 * e retenta UMA VEZ. Se o refresh falhar, propaga ApiError(401).
 */
export async function apiFetch(
  path: string,
  opts: RequestOptions = {},
): Promise<Response> {
  const { accessToken, onTokenRefreshed, _retryAfterRefresh, ...init } = opts;
  const headers = new Headers(init.headers ?? {});
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (!headers.has("Content-Type") && init.body && typeof init.body === "string") {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });

  if (res.status === 401 && !_retryAfterRefresh && onTokenRefreshed) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      onTokenRefreshed(refreshed);
      return apiFetch(path, {
        ...opts,
        accessToken: refreshed.access_token,
        _retryAfterRefresh: true,
      });
    }
  }

  return res;
}

/** Chama `/api/auth/refresh` (Route Handler). Retorna null em falha. */
export async function tryRefresh(): Promise<AuthSessionPayload | null> {
  try {
    const res = await fetch("/api/auth/refresh", { method: "POST" });
    if (!res.ok) return null;
    return (await res.json()) as AuthSessionPayload;
  } catch {
    return null;
  }
}

async function postJsonLocal<T>(
  path: string,
  body: Record<string, unknown>,
): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await parseJsonSafe(res);
  if (!res.ok) {
    throw new ApiError(res.status, payload);
  }
  return payload as T;
}

/** Chama `/api/auth/login` (Route Handler local). */
export function login(body: {
  email: string;
  password: string;
  tenant_slug?: string;
}): Promise<AuthSessionPayload> {
  return postJsonLocal<AuthSessionPayload>("/api/auth/login", body);
}

/** Chama `/api/auth/signup` (Route Handler local). */
export function signup(body: {
  tenant_name: string;
  tenant_slug: string;
  name: string;
  email: string;
  password: string;
}): Promise<AuthSessionPayload> {
  return postJsonLocal<AuthSessionPayload>("/api/auth/signup", body);
}

/** Chama `/api/auth/logout` (Route Handler local). Nunca lanca. */
export async function logout(): Promise<void> {
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } catch {
    // ignorar; logout client-side roda mesmo assim.
  }
}
