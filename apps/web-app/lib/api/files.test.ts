import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildListQuery,
  FILE_KIND_LABEL,
  FilesApiError,
  UI_FILTER_KINDS,
  formatBytes,
  getFileDownloadUrl,
  getFileKindLabel,
  listFiles,
} from "./files";

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
  it("usa defaults page=1 e page_size=20", () => {
    const sp = new URLSearchParams(buildListQuery({}));
    expect(sp.get("page")).toBe("1");
    expect(sp.get("page_size")).toBe("20");
  });

  it("inclui kind, company, from e to quando informados", () => {
    const qs = buildListQuery({
      page: 3,
      pageSize: 50,
      kind: "export",
      companyId: "cmp-1",
      from: "2026-01-01T00:00:00.000Z",
      to: "2026-02-01T00:00:00.000Z",
    });
    const sp = new URLSearchParams(qs);
    expect(sp.get("page")).toBe("3");
    expect(sp.get("page_size")).toBe("50");
    expect(sp.get("kind")).toBe("export");
    expect(sp.get("company")).toBe("cmp-1");
    expect(sp.get("from")).toBe("2026-01-01T00:00:00.000Z");
    expect(sp.get("to")).toBe("2026-02-01T00:00:00.000Z");
  });

  it("omite filtros nao informados", () => {
    const sp = new URLSearchParams(buildListQuery({ page: 1 }));
    expect(sp.has("kind")).toBe(false);
    expect(sp.has("company")).toBe(false);
    expect(sp.has("from")).toBe(false);
    expect(sp.has("to")).toBe(false);
  });
});

describe("listFiles", () => {
  it("monta GET /files com Authorization e devolve o envelope", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        items: [],
        page: 1,
        page_size: 20,
        total: 0,
      }),
    );
    const result = await listFiles(
      { page: 1, pageSize: 20, kind: "nfse_xml" },
      { accessToken: "tok-abc" },
    );
    expect(result.total).toBe(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain("/files?");
    expect(String(url)).toContain("kind=nfse_xml");
    const headers = new Headers((init as RequestInit).headers);
    expect(headers.get("Authorization")).toBe("Bearer tok-abc");
  });

  it("mapeia 403 para forbidden", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response("forbidden", { status: 403 }),
    );
    await expect(
      listFiles({}, { accessToken: "tok" }),
    ).rejects.toMatchObject({
      name: "FilesApiError",
      code: "forbidden",
      status: 403,
    });
  });

  it("mapeia 422 para validation_error", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "invalid" }), {
        status: 422,
        headers: { "content-type": "application/json" },
      }),
    );
    await expect(
      listFiles({ kind: "export" }, { accessToken: "tok" }),
    ).rejects.toMatchObject({ code: "validation_error" });
  });

  it("encapsula erro de rede como code=network", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("boom"));
    await expect(
      listFiles({}, { accessToken: "tok" }),
    ).rejects.toMatchObject({ code: "network", status: 0 });
  });
});

describe("getFileDownloadUrl", () => {
  it("monta GET /files/{id}/url e devolve url+expires", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        url: "https://s3.example.com/presigned?X-Amz-Signature=abc",
        expires_in: 3600,
        expires_at: "2026-04-22T11:00:00Z",
      }),
    );
    const result = await getFileDownloadUrl("file-1", { accessToken: "tok" });
    expect(result.url).toContain("X-Amz-Signature");
    expect(result.expires_in).toBe(3600);
    const [url] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain("/files/file-1/url");
  });

  it("mapeia 404 para not_found", async () => {
    fetchMock.mockResolvedValueOnce(new Response("", { status: 404 }));
    await expect(
      getFileDownloadUrl("missing", { accessToken: "tok" }),
    ).rejects.toMatchObject({ code: "not_found", status: 404 });
  });

  it("mapeia 502 para presign_unavailable", async () => {
    fetchMock.mockResolvedValueOnce(new Response("", { status: 502 }));
    await expect(
      getFileDownloadUrl("file-1", { accessToken: "tok" }),
    ).rejects.toMatchObject({ code: "presign_unavailable" });
  });
});

describe("helpers", () => {
  it("formatBytes devolve rotulo humano", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(500)).toBe("500 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(1024 * 1024 * 3.5)).toBe("3.5 MB");
  });

  it("formatBytes devolve em-dash para valores invalidos", () => {
    expect(formatBytes(Number.NaN)).toBe("—");
    expect(formatBytes(-1)).toBe("—");
  });

  it("UI_FILTER_KINDS oculta pfx e other", () => {
    expect(UI_FILTER_KINDS).not.toContain("pfx");
    expect(UI_FILTER_KINDS).not.toContain("other");
    expect(UI_FILTER_KINDS).toContain("nfse_xml");
    expect(UI_FILTER_KINDS).toContain("export");
  });

  it("FILE_KIND_LABEL cobre todos os kinds", () => {
    expect(FILE_KIND_LABEL.nfse_xml).toBeTruthy();
    expect(FILE_KIND_LABEL.export).toBeTruthy();
    expect(FILE_KIND_LABEL.pfx).toBeTruthy();
    expect(FILE_KIND_LABEL.report).toBeTruthy();
    expect(FILE_KIND_LABEL.other).toBeTruthy();
  });

  it("getFileKindLabel distingue Excel, ZIP e export generico", () => {
    expect(
      getFileKindLabel({ kind: "export", object_key: "exports/arquivo.XLSX" }),
    ).toBe("Excel NFS-e");
    expect(
      getFileKindLabel({ kind: "export", object_key: "exports/xml.zip" }),
    ).toBe("XML (ZIP)");
    expect(
      getFileKindLabel({ kind: "export", object_key: "exports/arquivo.bin" }),
    ).toBe("Export");
    expect(
      getFileKindLabel({ kind: "nfse_xml", object_key: "xml/1.xml" }),
    ).toBe("XML (NFS-e)");
  });

  it("FilesApiError carrega code e status", () => {
    const err = new FilesApiError(404, "not_found", "x");
    expect(err.status).toBe(404);
    expect(err.code).toBe("not_found");
  });
});
