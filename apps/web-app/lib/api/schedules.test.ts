import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/auth/api-client";

import {
  createSchedule,
  deleteSchedule,
  extractErrorDetail,
  listSchedulePresets,
  listSchedules,
  toggleSchedule,
  updateSchedule,
} from "./schedules";

type FetchMock = ReturnType<typeof vi.fn>;

function mockResponse(body: unknown, init: ResponseInit = {}): Response {
  const isText = typeof body === "string";
  const payload = isText ? (body as string) : JSON.stringify(body);
  return new Response(payload, {
    status: 200,
    headers: { "Content-Type": isText ? "text/plain" : "application/json" },
    ...init,
  });
}

const ctx = { accessToken: "tok" };

describe("schedules api client", () => {
  let fetchMock: FetchMock;

  beforeEach(() => {
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("listSchedules builds query with page/page_size/enabled", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse({ items: [], page: 1, page_size: 50, total: 0 }),
    );
    await listSchedules({ page: 2, pageSize: 20, enabled: true }, ctx);
    const [url] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/schedules?");
    expect(String(url)).toContain("page=2");
    expect(String(url)).toContain("page_size=20");
    expect(String(url)).toContain("enabled=true");
  });

  it("listSchedules omits enabled when null/undefined", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse({ items: [], page: 1, page_size: 50, total: 0 }),
    );
    await listSchedules({}, ctx);
    const [url] = fetchMock.mock.calls[0];
    expect(String(url)).not.toContain("enabled=");
  });

  it("sends Authorization header when access token is set", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse({ items: [], page: 1, page_size: 50, total: 0 }),
    );
    await listSchedules({}, { accessToken: "abc" });
    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer abc");
  });

  it("listSchedulePresets unwraps items", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        items: [
          {
            id: "daily_03",
            label: "Diario as 03:00",
            cron_expr: "0 3 * * *",
            description: "",
          },
        ],
      }),
    );
    const out = await listSchedulePresets(ctx);
    expect(out).toHaveLength(1);
    expect(out[0].cron_expr).toBe("0 3 * * *");
  });

  it("createSchedule posts JSON body and returns schedule", async () => {
    const schedule = {
      id: "11111111-1111-1111-1111-111111111111",
      tenant_id: "tid",
      company_id: null,
      cron_expr: "0 3 * * *",
      timezone: "America/Sao_Paulo",
      enabled: true,
      last_run_at: null,
      next_run_at: "2026-01-02T06:00:00Z",
      created_by_user_id: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    fetchMock.mockResolvedValueOnce(mockResponse(schedule, { status: 201 }));
    const out = await createSchedule(
      { cron_expr: "0 3 * * *", timezone: "America/Sao_Paulo" },
      ctx,
    );
    expect(out.id).toBe(schedule.id);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.body).toContain("cron_expr");
  });

  it("toggleSchedule sends PATCH with enabled only", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        id: "s1",
        tenant_id: "t1",
        company_id: null,
        cron_expr: "0 3 * * *",
        timezone: "UTC",
        enabled: false,
        last_run_at: null,
        next_run_at: null,
        created_by_user_id: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      }),
    );
    await toggleSchedule("s1", false, ctx);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/schedules\/s1$/);
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({ enabled: false }));
  });

  it("updateSchedule throws ApiError on 400", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse(
        { detail: "cron_expr invalida" },
        { status: 400, headers: { "Content-Type": "application/json" } },
      ),
    );
    await expect(
      updateSchedule("s1", { cron_expr: "bad" }, ctx),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("deleteSchedule resolves on 204 without body", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(deleteSchedule("s1", ctx)).resolves.toBeUndefined();
  });

  it("deleteSchedule throws ApiError on 403", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse(
        { detail: "forbidden" },
        { status: 403, headers: { "Content-Type": "application/json" } },
      ),
    );
    await expect(deleteSchedule("s1", ctx)).rejects.toBeInstanceOf(ApiError);
  });
});

describe("extractErrorDetail", () => {
  it("returns detail from FastAPI object", () => {
    const err = new ApiError(400, { detail: "cron invalida" });
    expect(extractErrorDetail(err)).toBe("cron invalida");
  });
  it("returns raw string detail", () => {
    const err = new ApiError(400, "raw");
    expect(extractErrorDetail(err)).toBe("raw");
  });
  it("returns null for non ApiError", () => {
    expect(extractErrorDetail(new Error("x"))).toBeNull();
  });
});
