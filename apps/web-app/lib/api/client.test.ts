import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "./client";

type FetchArgs = Parameters<typeof fetch>;

function jsonResponse(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

describe("createApiClient", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("injeta Authorization: Bearer quando ha token", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ status: "ok" }));

    const client = createApiClient({
      baseUrl: "http://api.test",
      getAccessToken: () => "tkn-1",
      fetch: fetchMock as unknown as typeof fetch,
    });

    const res = await client.GET("/health");
    expect(res.data).toEqual({ status: "ok" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [req] = fetchMock.mock.calls[0] as FetchArgs;
    const request = req as Request;
    expect(request.headers.get("Authorization")).toBe("Bearer tkn-1");
  });

  it("nao injeta Authorization quando getAccessToken retorna null", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ status: "ok" }));

    const client = createApiClient({
      baseUrl: "http://api.test",
      getAccessToken: () => null,
      fetch: fetchMock as unknown as typeof fetch,
    });

    await client.GET("/health");
    const [req] = fetchMock.mock.calls[0] as FetchArgs;
    const request = req as Request;
    expect(request.headers.get("Authorization")).toBeNull();
  });

  it("retenta uma unica vez com novo token apos 401 + refresh", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ detail: "unauth" }, 401))
      .mockResolvedValueOnce(jsonResponse({ status: "ok" }));

    const refresh = vi.fn().mockResolvedValue({
      access_token: "tkn-2",
      expires_in: 600,
      user: { userId: "u1", tenantId: "t1", role: "owner" },
    });
    const onTokenRefreshed = vi.fn();
    const onAuthFailure = vi.fn();

    const client = createApiClient({
      baseUrl: "http://api.test",
      getAccessToken: () => "tkn-1",
      refresh,
      onTokenRefreshed,
      onAuthFailure,
      fetch: fetchMock as unknown as typeof fetch,
    });

    const res = await client.GET("/auth/me");

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(onTokenRefreshed).toHaveBeenCalledTimes(1);
    expect(onAuthFailure).not.toHaveBeenCalled();
    expect(res.response.status).toBe(200);

    const retryArgs = fetchMock.mock.calls[1] as [string, RequestInit];
    const headers = new Headers(retryArgs[1].headers);
    expect(headers.get("Authorization")).toBe("Bearer tkn-2");
    expect(headers.get("x-ds09-retry")).toBe("1");
  });

  it("chama onAuthFailure quando o refresh falha", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "unauth" }, 401));

    const refresh = vi.fn().mockResolvedValue(null);
    const onAuthFailure = vi.fn();

    const client = createApiClient({
      baseUrl: "http://api.test",
      getAccessToken: () => "tkn-1",
      refresh,
      onAuthFailure,
      fetch: fetchMock as unknown as typeof fetch,
    });

    const res = await client.GET("/auth/me");

    expect(refresh).toHaveBeenCalledTimes(1);
    expect(onAuthFailure).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(res.response.status).toBe(401);
  });

  it("nao entra em loop — request com x-ds09-retry=1 nao dispara refresh", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "unauth" }, 401));
    const refresh = vi.fn();
    const onAuthFailure = vi.fn();

    const client = createApiClient({
      baseUrl: "http://api.test",
      getAccessToken: () => "tkn-1",
      refresh,
      onAuthFailure,
      fetch: fetchMock as unknown as typeof fetch,
    });

    await client.GET("/health", {
      headers: { "x-ds09-retry": "1" },
    });

    expect(refresh).not.toHaveBeenCalled();
    expect(onAuthFailure).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
