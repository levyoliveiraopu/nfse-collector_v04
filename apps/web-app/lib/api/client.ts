/**
 * Cliente HTTP tipado (DS-09) baseado em `openapi-fetch`.
 *
 * Diferente do `apiFetch` do APP-01 (que e um helper de baixo nivel usado
 * pelos clients manuais legados), este cliente usa `paths` gerado pelo
 * `openapi-typescript` — os endpoints e schemas sao validados em tempo de
 * compilacao contra o OpenAPI da API.
 *
 * Convencoes:
 * - `createApiClient({ getAccessToken, onTokenRefreshed, onAuthFailure })`
 *   devolve um cliente fresh (usado no AuthProvider + nos testes).
 * - `getApiClient()` devolve um cliente singleton sem auth — util para
 *   chamadas publicas como `/health`. Pode ser reconfigurado no boot via
 *   `configureApiClient(...)`.
 * - Middlewares encadeados:
 *     1. injecao de `Authorization: Bearer <token>` quando ha token;
 *     2. retry unico em 401 com refresh (`tryRefresh` da APP-01). Se o
 *        refresh falhar, chama `onAuthFailure` (default: redirect hard
 *        para `/login`). O flag `x-ds09-retry: 1` no request evita loop.
 */
import createClient, {
  type Client,
  type Middleware,
} from "openapi-fetch";

import { tryRefresh } from "@/lib/auth/api-client";
import type { AuthSessionPayload } from "@/lib/auth/types";

import type { paths } from "./generated/schema";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const RETRY_HEADER = "x-ds09-retry";

export type ApiClient = Client<paths>;

export interface CreateApiClientOptions {
  /** Base URL da API. Default: NEXT_PUBLIC_API_BASE_URL. */
  baseUrl?: string;
  /** Retorna o access token vigente (ou null quando anonimo). */
  getAccessToken?: () => string | null;
  /** Chamado quando o refresh bem-sucedido entrega um novo par de tokens. */
  onTokenRefreshed?: (payload: AuthSessionPayload) => void;
  /** Chamado quando o refresh falha em 401. Default: redirect /login. */
  onAuthFailure?: () => void;
  /** Override da funcao de refresh (uso em testes). */
  refresh?: () => Promise<AuthSessionPayload | null>;
  /** Override de `fetch` (SSR/testes). */
  fetch?: typeof fetch;
}

function defaultAuthFailure() {
  if (typeof window !== "undefined") {
    window.location.href = "/login";
  }
}

/** Cria um cliente novo com auth e interceptor de refresh. */
export function createApiClient(
  opts: CreateApiClientOptions = {},
): ApiClient {
  const {
    baseUrl = API_BASE_URL,
    getAccessToken,
    onTokenRefreshed,
    onAuthFailure = defaultAuthFailure,
    refresh = tryRefresh,
    fetch: fetchImpl,
  } = opts;

  const client = createClient<paths>({
    baseUrl,
    ...(fetchImpl ? { fetch: fetchImpl } : {}),
  });

  const authMiddleware: Middleware = {
    async onRequest({ request }) {
      if (!getAccessToken) return undefined;
      const token = getAccessToken();
      if (token && !request.headers.has("Authorization")) {
        request.headers.set("Authorization", `Bearer ${token}`);
      }
      return request;
    },
    async onResponse({ request, response }) {
      if (response.status !== 401) return undefined;
      if (request.headers.get(RETRY_HEADER) === "1") return undefined;

      const refreshed = await refresh();
      if (!refreshed) {
        onAuthFailure();
        return undefined;
      }
      onTokenRefreshed?.(refreshed);

      const retryHeaders = new Headers(request.headers);
      retryHeaders.set("Authorization", `Bearer ${refreshed.access_token}`);
      retryHeaders.set(RETRY_HEADER, "1");
      const retryInit: RequestInit = {
        method: request.method,
        headers: retryHeaders,
      };
      if (request.method !== "GET" && request.method !== "HEAD") {
        retryInit.body = await request.clone().text();
      }
      const retryRes = await (fetchImpl ?? fetch)(request.url, retryInit);
      return retryRes;
    },
  };

  client.use(authMiddleware);
  return client;
}

let singleton: ApiClient | null = null;
let singletonOpts: CreateApiClientOptions = {};

/** Reconfigura o singleton (ex: ao logar/logout). */
export function configureApiClient(opts: CreateApiClientOptions): ApiClient {
  singletonOpts = opts;
  singleton = createApiClient(opts);
  return singleton;
}

/** Devolve o cliente singleton (sem auth por default). */
export function getApiClient(): ApiClient {
  if (!singleton) singleton = createApiClient(singletonOpts);
  return singleton;
}

/** Reseta o singleton — util em testes. */
export function __resetApiClientForTests(): void {
  singleton = null;
  singletonOpts = {};
}
