import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ExecutionsApiError,
  buildItemsQuery,
  buildListQuery,
  computeProgress,
  createExecutions,
  decideExecutionBadge,
  getExecution,
  isTerminalStatus,
  listExecutionItems,
  listExecutions,
} from "./executions";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
    ...init,
  });
}

describe("buildListQuery", () => {
  it("aplica defaults (page=1, page_size=20)", () => {
    const qs = buildListQuery({});
    const sp = new URLSearchParams(qs);
    expect(sp.get("page")).toBe("1");
    expect(sp.get("page_size")).toBe("20");
  });

  it("serializa filtros presentes", () => {
    const qs = buildListQuery({
      page: 3,
      pageSize: 10,
      companyId: "c1",
      status: "succeeded",
      from: "2026-04-01T00:00:00Z",
      to: "2026-04-17T00:00:00Z",
    });
    const sp = new URLSearchParams(qs);
    expect(sp.get("page")).toBe("3");
    expect(sp.get("page_size")).toBe("10");
    expect(sp.get("company_id")).toBe("c1");
    expect(sp.get("status")).toBe("succeeded");
    expect(sp.get("from")).toBe("2026-04-01T00:00:00Z");
    expect(sp.get("to")).toBe("2026-04-17T00:00:00Z");
  });
});

describe("buildItemsQuery", () => {
  it("inclui status/nsu quando presentes", () => {
    const sp = new URLSearchParams(
      buildItemsQuery({ page: 2, pageSize: 50, status: "failed", nsu: 123 }),
    );
    expect(sp.get("page")).toBe("2");
    expect(sp.get("status")).toBe("failed");
    expect(sp.get("nsu")).toBe("123");
  });
});

describe("listExecutions", () => {
  it("monta GET /executions com Authorization", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ items: [], page: 1, page_size: 20, total: 0 }),
    );
    const res = await listExecutions({}, { accessToken: "tok" });
    expect(res.total).toBe(0);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain("/executions?");
    expect(new Headers((init as RequestInit).headers).get("Authorization")).toBe(
      "Bearer tok",
    );
  });

  it("transforma 403 em ExecutionsApiError.forbidden", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response("nope", { status: 403 }),
    );
    await expect(
      listExecutions({}, { accessToken: "t" }),
    ).rejects.toMatchObject({ code: "forbidden", status: 403 });
  });
});

describe("getExecution", () => {
  it("404 vira ExecutionsApiError.not_found", async () => {
    fetchMock.mockResolvedValueOnce(new Response("", { status: 404 }));
    await expect(
      getExecution("any", { accessToken: "t" }),
    ).rejects.toMatchObject({ code: "not_found" });
  });
});

describe("listExecutionItems", () => {
  it("usa endpoint /executions/{id}/items", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ items: [], page: 1, page_size: 50, total: 0 }),
    );
    await listExecutionItems("xyz", { status: "ok" }, { accessToken: "t" });
    const url = String(fetchMock.mock.calls[0]![0]);
    expect(url).toContain("/executions/xyz/items?");
    expect(url).toContain("status=ok");
  });
});

describe("createExecutions", () => {
  it("POSTa JSON com company_ids + periodo + dry_run", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        created: [
          {
            execution_id: "e1",
            company_id: "c1",
            status: "queued",
            job_id: "j1",
            enqueue_error: null,
          },
        ],
      }),
    );

    const res = await createExecutions(
      {
        company_ids: ["c1"],
        period_start: "2026-04-01",
        period_end: "2026-04-17",
        dry_run: true,
      },
      { accessToken: "t" },
    );

    expect(res.created).toHaveLength(1);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain("/executions");
    expect((init as RequestInit).method).toBe("POST");
    const body = JSON.parse(String((init as RequestInit).body));
    expect(body.company_ids).toEqual(["c1"]);
    expect(body.dry_run).toBe(true);
  });

  it("traduz 422 credential_missing_or_expired preservando company_ids", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: {
            error: "credential_missing_or_expired",
            company_ids: ["c1", "c2"],
          },
        }),
        {
          status: 422,
          headers: { "content-type": "application/json" },
        },
      ),
    );

    try {
      await createExecutions(
        {
          company_ids: ["c1", "c2"],
          period_start: "2026-04-01",
          period_end: "2026-04-17",
        },
        { accessToken: "t" },
      );
      expect.fail("devia ter lancado");
    } catch (err) {
      expect(err).toBeInstanceOf(ExecutionsApiError);
      const api = err as ExecutionsApiError;
      expect(api.code).toBe("credential_missing_or_expired");
      expect(api.extra.companyIds).toEqual(["c1", "c2"]);
    }
  });

  it("traduz 422 companies_not_found", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: { error: "companies_not_found", missing: ["c9"] },
        }),
        { status: 422, headers: { "content-type": "application/json" } },
      ),
    );

    const p = createExecutions(
      {
        company_ids: ["c9"],
        period_start: "2026-04-01",
        period_end: "2026-04-17",
      },
      { accessToken: "t" },
    );
    await expect(p).rejects.toMatchObject({ code: "companies_not_found" });
  });

  it("502 vira queue_unavailable", async () => {
    fetchMock.mockResolvedValueOnce(new Response("", { status: 502 }));
    await expect(
      createExecutions(
        {
          company_ids: ["c1"],
          period_start: "2026-04-01",
          period_end: "2026-04-17",
        },
        { accessToken: "t" },
      ),
    ).rejects.toMatchObject({ code: "queue_unavailable" });
  });
});

describe("decideExecutionBadge", () => {
  it("cobre as 6 variantes de status", () => {
    expect(decideExecutionBadge("queued")).toBe("pending");
    expect(decideExecutionBadge("running")).toBe("processing");
    expect(decideExecutionBadge("succeeded")).toBe("success");
    expect(decideExecutionBadge("failed")).toBe("failed");
    expect(decideExecutionBadge("cancelled")).toBe("blocked");
    expect(decideExecutionBadge("partial")).toBe("warning");
  });
});

describe("isTerminalStatus", () => {
  it("marca succeeded/failed/cancelled/partial como terminais", () => {
    expect(isTerminalStatus("queued")).toBe(false);
    expect(isTerminalStatus("running")).toBe(false);
    expect(isTerminalStatus("succeeded")).toBe(true);
    expect(isTerminalStatus("failed")).toBe(true);
    expect(isTerminalStatus("cancelled")).toBe(true);
    expect(isTerminalStatus("partial")).toBe(true);
  });
});

describe("computeProgress", () => {
  it("calcula percentual e garante total >= processed", () => {
    const p = computeProgress({
      items_total: 10,
      items_ok: 4,
      items_fail: 2,
      status: "running",
    });
    expect(p.processed).toBe(6);
    expect(p.total).toBe(10);
    expect(p.percent).toBe(60);
  });

  it("retorna 0% quando total=0 (execucao recem-criada)", () => {
    const p = computeProgress({
      items_total: 0,
      items_ok: 0,
      items_fail: 0,
      status: "queued",
    });
    expect(p.percent).toBe(0);
  });

  it("clampa em 100% quando processed > total (corner case)", () => {
    const p = computeProgress({
      items_total: 5,
      items_ok: 4,
      items_fail: 4,
      status: "partial",
    });
    expect(p.percent).toBe(100);
  });
});
