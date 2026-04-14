/**
 * Utilitarios server-side (Route Handlers) para proxy dos endpoints de
 * autenticacao (APP-01). Mantem o refresh token em cookie httpOnly,
 * nunca o devolvendo ao cliente.
 */
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import type { AuthSessionPayload, AuthTokenResponse } from "./types";

export const REFRESH_COOKIE_NAME = "nfse_refresh";

/** Base URL da API FastAPI. Prefere `API_BASE_URL` server-side, cai no publico. */
export function apiBaseUrl(): string {
  return (
    process.env.API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://localhost:8000"
  );
}

/**
 * Converte a resposta raw da API em payload seguro para o cliente e prepara
 * o Set-Cookie do refresh. Retorna ambos para o Route Handler montar a
 * resposta final.
 */
export function sessionFromApiResponse(
  raw: AuthTokenResponse,
): AuthSessionPayload {
  return {
    access_token: raw.access_token,
    expires_in: raw.expires_in,
    user: {
      userId: raw.user_id,
      tenantId: raw.tenant_id,
      role: raw.role,
    },
  };
}

/** Opcoes do cookie httpOnly que guarda o refresh token. */
export function refreshCookieOptions(maxAgeSeconds: number) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: maxAgeSeconds,
  };
}

/** Default de 7 dias (alinhado com API_REFRESH_TOKEN_TTL_DAYS). */
const DEFAULT_REFRESH_MAX_AGE = 60 * 60 * 24 * 7;

/**
 * Monta NextResponse contendo a sessao (sem refresh no body) e seta o cookie
 * httpOnly com o refresh token recem emitido pela API.
 */
export function buildSessionResponse(
  raw: AuthTokenResponse,
  init: { status?: number } = {},
): NextResponse<AuthSessionPayload> {
  const session = sessionFromApiResponse(raw);
  const response = NextResponse.json(session, { status: init.status ?? 200 });
  response.cookies.set(
    REFRESH_COOKIE_NAME,
    raw.refresh_token,
    refreshCookieOptions(DEFAULT_REFRESH_MAX_AGE),
  );
  return response;
}

/** Le o cookie httpOnly atual. */
export function readRefreshCookie(): string | undefined {
  return cookies().get(REFRESH_COOKIE_NAME)?.value;
}

/** Remove o cookie httpOnly na resposta. */
export function clearRefreshCookie(response: NextResponse): NextResponse {
  response.cookies.set(REFRESH_COOKIE_NAME, "", {
    ...refreshCookieOptions(0),
    maxAge: 0,
  });
  return response;
}

/** Faz fetch contra a API FastAPI passando um JSON body e devolve a resposta. */
export async function proxyToApi(
  path: string,
  body: unknown,
): Promise<Response> {
  return fetch(`${apiBaseUrl()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    // Route Handlers rodam em runtime Node; nao queremos cache.
    cache: "no-store",
  });
}
