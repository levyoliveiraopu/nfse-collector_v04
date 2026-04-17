import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  acknowledgeOccurrence,
  assignOccurrence,
  buildListQuery,
  getOccurrence,
  isTerminal,
  listOccurrences,
  resolveOccurrence,
} from "./occurrences";
import { ApiError } from "@/lib/auth/api-client";

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

function fakeOccurrence() {
  return {
    id: "occ-1",
    tenant_id: "t-1",
    company_id: "c-1",
    execution_id: null,
    severity: "error",
    code: "CERT_EXPIRED",
    title: "Certificado A1 expirado",
    detail: null,
    status: "open",
    assignee_user_id: null,
    first_seen_at: "2026-04-17T10:00:00Z",
    last_seen_at: "2026-04-17T10:00:00Z",
    resolved_at: null,
    created_at: "2026-04-17T10:00:00Z",
    updated_at: "2026-04-17T10:00:00Z",
  };
}

describe("buildListQuery", () => {
  it("converte pageIndex 0-based em page 1-based", () => {
    const sp = new URLSearchParams(
      buildListQuery({
        pagination: { pageIndex: 0, pageSize: 20 },
        sort: null,
        filters: {},
      }),
    );
    expect(sp.get("page")).toBe("1");
    expect(sp.get("page_size")).toBe("20");
  });

  it("inclui status, severity e company_id quando presentes", () => {
    const sp = new URLSearchParams(
      buildListQuery({
        pagination: { pageIndex: 1, pageSize: 50 },
        sort: null,
        filters: {
          status: "open",
          severity: "critical",
          company_id: "c-1",
        },
      }),
    );
    expect(sp.get("page")).toBe("2");
    expect(sp.get("status")).toBe("open");
    expect(sp.get("severity")).toBe("critical");
    expect(sp.get("company_id")).toBe("c-1");
  });

  it("faz trim de company_id e omite vazios", () => {
    const sp = new URLSearchParams(
      buildListQuery({
        pagination: { pageIndex: 0, pageSize: 10 },
        sort: null,
        filters: { company_id: "  cid  ", severity: "" },
      }),
    );
    expect(sp.get("company_id")).toBe("cid");
    expect(sp.has("severity")).toBe(false);
  });
});

describe("listOccurrences", () => {
  it("faz GET /occurrences com Authorization e devolve rows+total", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        items: [fakeOccurrence()],
        page: 1,
        page_size: 20,
        total: 1,
      }),
    );
    const result = await listOccurrences(
      {
        pagination: { pageIndex: 0, pageSize: 20 },
        sort: null,
        filters: { status: "open" },
      },
      { accessToken: "tok" },
    );
    expect(result.total).toBe(1);
    expect(result.rows).toHaveLength(1);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain("/occurrences?");
    expect(String(url)).toContain("status=open");
    const headers = new Headers((init as RequestInit).headers);
    expect(headers.get("Authorization")).toBe("Bearer tok");
  });

  it("propaga ApiError em 403", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response("forbidden", { status: 403 }),
    );
    await expect(
      listOccurrences(
        {
          pagination: { pageIndex: 0, pageSize: 10 },
          sort: null,
          filters: {},
        },
        { accessToken: null },
      ),
    ).rejects.toBeInstanceOf(ApiError);
  });
});

describe("getOccurrence", () => {
  it("faz GET /occurrences/{id} e devolve a entidade", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(fakeOccurrence()));
    const occ = await getOccurrence("occ-1", { accessToken: "x" });
    expect(occ.id).toBe("occ-1");
    expect(String(fetchMock.mock.calls[0]![0])).toContain(
      "/occurrences/occ-1",
    );
  });

  it("lanca ApiError em 404", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response('{"detail":"ocorrencia nao encontrada"}', {
        status: 404,
        headers: { "content-type": "application/json" },
      }),
    );
    await expect(
      getOccurrence("occ-1", { accessToken: "x" }),
    ).rejects.toMatchObject({ status: 404 });
  });
});

describe("acknowledgeOccurrence", () => {
  it("envia POST /occurrences/{id}/acknowledge e devolve a entidade atualizada", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ ...fakeOccurrence(), status: "ack" }),
    );
    const updated = await acknowledgeOccurrence("occ-1", {
      accessToken: "x",
    });
    expect(updated.status).toBe("ack");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain("/occurrences/occ-1/acknowledge");
    expect((init as RequestInit).method).toBe("POST");
  });
});

describe("resolveOccurrence", () => {
  it("envia POST /resolve com nota em JSON", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ...fakeOccurrence(),
        status: "resolved",
        resolved_at: "2026-04-17T11:00:00Z",
      }),
    );
    await resolveOccurrence(
      "occ-1",
      { note: "reprocessei e deu certo" },
      { accessToken: "x" },
    );
    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect(init.method).toBe("POST");
    const headers = new Headers(init.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(JSON.parse(init.body as string)).toEqual({
      note: "reprocessei e deu certo",
    });
  });

  it("lanca ApiError em 422 (nota vazia no backend)", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response('{"detail":"note required"}', {
        status: 422,
        headers: { "content-type": "application/json" },
      }),
    );
    await expect(
      resolveOccurrence(
        "occ-1",
        { note: "" },
        { accessToken: "x" },
      ),
    ).rejects.toMatchObject({ status: 422 });
  });
});

describe("assignOccurrence", () => {
  it("envia POST /assign com assignee_user_id", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ ...fakeOccurrence(), assignee_user_id: "u-1" }),
    );
    await assignOccurrence(
      "occ-1",
      { assignee_user_id: "u-1" },
      { accessToken: "x" },
    );
    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      assignee_user_id: "u-1",
    });
  });

  it("lanca ApiError em 404 (user de outro tenant)", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response('{"detail":"usuario nao e membro do tenant"}', {
        status: 404,
        headers: { "content-type": "application/json" },
      }),
    );
    await expect(
      assignOccurrence(
        "occ-1",
        { assignee_user_id: "u-1" },
        { accessToken: "x" },
      ),
    ).rejects.toMatchObject({ status: 404 });
  });
});

describe("isTerminal", () => {
  it.each([
    ["open", false],
    ["ack", false],
    ["snoozed", false],
    ["resolved", true],
    ["ignored", true],
  ] as const)("isTerminal(%s) = %s", (status, expected) => {
    expect(isTerminal(status)).toBe(expected);
  });
});
