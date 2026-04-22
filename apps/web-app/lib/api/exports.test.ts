import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ExportsApiError,
  createExport,
  getExport,
  isTerminalExportStatus,
} from "./exports";

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

describe("createExport", () => {
  it("monta POST /exports com payload JSON e Authorization", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          export_id: "exp-1",
          status: "queued",
          job_id: "rq-123",
          enqueue_error: null,
        },
        { status: 201 },
      ),
    );
    const result = await createExport(
      {
        company_id: "cmp-1",
        period_start: "2026-04-01",
        period_end: "2026-04-30",
      },
      { accessToken: "tok" },
    );
    expect(result.export_id).toBe("exp-1");
    expect(result.status).toBe("queued");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain("/exports");
    expect((init as RequestInit).method).toBe("POST");
    const body = JSON.parse(String((init as RequestInit).body));
    expect(body.company_id).toBe("cmp-1");
    expect(body.period_start).toBe("2026-04-01");
    expect(body.period_end).toBe("2026-04-30");
  });

  it("devolve failed quando backend marca enqueue_failed", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          export_id: "exp-2",
          status: "failed",
          job_id: null,
          enqueue_error: "enqueue_failed",
        },
        { status: 201 },
      ),
    );
    const result = await createExport(
      { company_id: "cmp-1", period_start: "2026-04-01", period_end: "2026-04-30" },
      { accessToken: "tok" },
    );
    expect(result.status).toBe("failed");
    expect(result.enqueue_error).toBe("enqueue_failed");
  });

  it("mapeia 422 com error=company_not_found", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: { error: "company_not_found", company_id: "cmp-x" },
        }),
        { status: 422, headers: { "content-type": "application/json" } },
      ),
    );
    await expect(
      createExport(
        { company_id: "cmp-x", period_start: "2026-04-01", period_end: "2026-04-30" },
        { accessToken: "tok" },
      ),
    ).rejects.toMatchObject({ code: "company_not_found" });
  });

  it("mapeia 502 para queue_unavailable", async () => {
    fetchMock.mockResolvedValueOnce(new Response("", { status: 502 }));
    await expect(
      createExport(
        { company_id: "cmp-1", period_start: "2026-04-01", period_end: "2026-04-30" },
        { accessToken: "tok" },
      ),
    ).rejects.toMatchObject({ code: "queue_unavailable" });
  });

  it("mapeia 403 para forbidden", async () => {
    fetchMock.mockResolvedValueOnce(new Response("", { status: 403 }));
    await expect(
      createExport(
        { company_id: "cmp-1", period_start: "2026-04-01", period_end: "2026-04-30" },
        { accessToken: "tok" },
      ),
    ).rejects.toMatchObject({ code: "forbidden" });
  });
});

describe("getExport", () => {
  it("devolve record com download_url quando ready", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        id: "exp-1",
        tenant_id: "t-1",
        company_id: "cmp-1",
        requested_by_user_id: "u-1",
        kind: "zip_xml",
        period_start: "2026-04-01",
        period_end: "2026-04-30",
        status: "ready",
        file_id: "file-1",
        items_count: 3,
        total_bytes: 1024,
        error_code: null,
        error_message: null,
        started_at: "2026-04-22T10:00:00Z",
        finished_at: "2026-04-22T10:01:00Z",
        created_at: "2026-04-22T10:00:00Z",
        updated_at: "2026-04-22T10:01:00Z",
        download_url: "https://s3.example.com/signed",
        expires_in: 3600,
      }),
    );
    const record = await getExport("exp-1", { accessToken: "tok" });
    expect(record.status).toBe("ready");
    expect(record.download_url).toBe("https://s3.example.com/signed");
  });

  it("mapeia 404 para not_found", async () => {
    fetchMock.mockResolvedValueOnce(new Response("", { status: 404 }));
    await expect(
      getExport("missing", { accessToken: "tok" }),
    ).rejects.toMatchObject({ code: "not_found" });
  });
});

describe("isTerminalExportStatus", () => {
  it("reconhece estados terminais", () => {
    expect(isTerminalExportStatus("ready")).toBe(true);
    expect(isTerminalExportStatus("failed")).toBe(true);
    expect(isTerminalExportStatus("empty")).toBe(true);
  });
  it("estados intermediarios nao sao terminais", () => {
    expect(isTerminalExportStatus("queued")).toBe(false);
    expect(isTerminalExportStatus("running")).toBe(false);
  });
});

describe("ExportsApiError", () => {
  it("carrega status e code", () => {
    const err = new ExportsApiError(502, "queue_unavailable", "x");
    expect(err.status).toBe(502);
    expect(err.code).toBe("queue_unavailable");
  });
});
