import * as React from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "./client";
import { useCompanies, useHealth } from "./hooks";

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  }
  return Wrapper;
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("hooks react-query tipados", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("useHealth devolve payload de /health", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ status: "ok" }));
    const api = createApiClient({
      baseUrl: "http://api.test",
      fetch: fetchMock as unknown as typeof fetch,
    });

    const { result } = renderHook(() => useHealth({ client: api }), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ status: "ok" });
  });

  it("useCompanies passa query string", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ items: [], page: 1, page_size: 25, total: 0 }),
    );
    const api = createApiClient({
      baseUrl: "http://api.test",
      fetch: fetchMock as unknown as typeof fetch,
    });

    const { result } = renderHook(
      () =>
        useCompanies(
          { status: "active", page: 1, page_size: 25 },
          { client: api },
        ),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [req] = fetchMock.mock.calls[0] as [Request];
    const url = new URL(req.url);
    expect(url.pathname).toBe("/companies");
    expect(url.searchParams.get("status")).toBe("active");
    expect(url.searchParams.get("page")).toBe("1");
    expect(url.searchParams.get("page_size")).toBe("25");
  });

  it("hooks propagam erro quando API retorna >=400", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "boom" }, 500));
    const api = createApiClient({
      baseUrl: "http://api.test",
      fetch: fetchMock as unknown as typeof fetch,
    });

    const { result } = renderHook(() => useHealth({ client: api }), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toMatch(/500|API error/);
  });
});
