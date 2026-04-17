/**
 * Hooks react-query base do cliente tipado (DS-09).
 *
 * Seguem a convencao do app: queries usam `useQuery` com `queryKey`
 * estavel e chamam o client tipado via `getApiClient()`. Cada hook
 * aceita override opcional (`client`) para facilitar testes sem tocar
 * no singleton.
 */
import { useQuery, type UseQueryOptions } from "@tanstack/react-query";

import { getApiClient, type ApiClient } from "./client";
import type { components, operations } from "./types";

export type HealthResponse =
  operations["health_health_get"]["responses"][200]["content"]["application/json"];
export type VersionResponse =
  operations["version_version_get"]["responses"][200]["content"]["application/json"];
export type MeResponse = components["schemas"]["MeOut"];
export type CompanyListResponse = components["schemas"]["CompanyListOut"];
export type ExecutionListResponse = components["schemas"]["ExecutionListOut"];

export type CompaniesQuery = NonNullable<
  operations["list_companies_companies_get"]["parameters"]["query"]
>;
export type ExecutionsQuery = NonNullable<
  operations["list_executions_executions_get"]["parameters"]["query"]
>;

type QueryOpts<T> = Omit<UseQueryOptions<T, Error>, "queryKey" | "queryFn">;

async function unwrap<T>(result: {
  data?: T;
  error?: unknown;
  response: Response;
}): Promise<T> {
  if (result.error !== undefined || !result.response.ok) {
    const err = new Error(
      typeof result.error === "string"
        ? result.error
        : `API error ${result.response.status}`,
    );
    (err as Error & { status?: number }).status = result.response.status;
    (err as Error & { detail?: unknown }).detail = result.error;
    throw err;
  }
  return result.data as T;
}

/** `GET /health` — prova do DoD "chamada real de /health". */
export function useHealth(
  options: QueryOpts<HealthResponse> & { client?: ApiClient } = {},
) {
  const { client, ...rest } = options;
  return useQuery<HealthResponse, Error>({
    queryKey: ["health"],
    queryFn: async () => {
      const api = client ?? getApiClient();
      const res = await api.GET("/health");
      return unwrap<HealthResponse>(res);
    },
    ...rest,
  });
}

/** `GET /version`. */
export function useVersion(
  options: QueryOpts<VersionResponse> & { client?: ApiClient } = {},
) {
  const { client, ...rest } = options;
  return useQuery<VersionResponse, Error>({
    queryKey: ["version"],
    queryFn: async () => {
      const api = client ?? getApiClient();
      const res = await api.GET("/version");
      return unwrap<VersionResponse>(res);
    },
    ...rest,
  });
}

/** `GET /auth/me` — identidade do usuario logado. */
export function useMe(
  options: QueryOpts<MeResponse> & { client?: ApiClient } = {},
) {
  const { client, ...rest } = options;
  return useQuery<MeResponse, Error>({
    queryKey: ["me"],
    queryFn: async () => {
      const api = client ?? getApiClient();
      const res = await api.GET("/auth/me");
      return unwrap<MeResponse>(res);
    },
    ...rest,
  });
}

/** `GET /companies` — lista paginada. */
export function useCompanies(
  query: CompaniesQuery = {},
  options: QueryOpts<CompanyListResponse> & { client?: ApiClient } = {},
) {
  const { client, ...rest } = options;
  return useQuery<CompanyListResponse, Error>({
    queryKey: ["companies:list", query],
    queryFn: async () => {
      const api = client ?? getApiClient();
      const res = await api.GET("/companies", { params: { query } });
      return unwrap<CompanyListResponse>(res);
    },
    ...rest,
  });
}

/** `GET /executions` — lista paginada. */
export function useExecutions(
  query: ExecutionsQuery = {},
  options: QueryOpts<ExecutionListResponse> & { client?: ApiClient } = {},
) {
  const { client, ...rest } = options;
  return useQuery<ExecutionListResponse, Error>({
    queryKey: ["executions:list", query],
    queryFn: async () => {
      const api = client ?? getApiClient();
      const res = await api.GET("/executions", { params: { query } });
      return unwrap<ExecutionListResponse>(res);
    },
    ...rest,
  });
}
