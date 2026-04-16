import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildListQuery,
  createCompany,
  deleteCompany,
  formatCnpj,
  getCompany,
  listCompanies,
  updateCompany,
} from "./companies";
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

describe("buildListQuery", () => {
  it("converte page-index 0-based em page 1-based", () => {
    const qs = buildListQuery({
      pagination: { pageIndex: 0, pageSize: 25 },
      sort: null,
      filters: {},
    });
    const sp = new URLSearchParams(qs);
    expect(sp.get("page")).toBe("1");
    expect(sp.get("page_size")).toBe("25");
  });

  it("inclui status quando filtro presente", () => {
    const qs = buildListQuery({
      pagination: { pageIndex: 2, pageSize: 50 },
      sort: null,
      filters: { status: "paused" },
    });
    const sp = new URLSearchParams(qs);
    expect(sp.get("page")).toBe("3");
    expect(sp.get("status")).toBe("paused");
  });

  it("normaliza UF para uppercase e trim", () => {
    const qs = buildListQuery({
      pagination: { pageIndex: 0, pageSize: 10 },
      sort: null,
      filters: { uf: "  sp  " },
    });
    expect(new URLSearchParams(qs).get("uf")).toBe("SP");
  });

  it("omite filtros vazios", () => {
    const qs = buildListQuery({
      pagination: { pageIndex: 0, pageSize: 10 },
      sort: null,
      filters: { uf: "", status: null },
    });
    const sp = new URLSearchParams(qs);
    expect(sp.has("uf")).toBe(false);
    expect(sp.has("status")).toBe(false);
  });

  it("nao inclui filtros que API-05 ainda nao suporta (ex: last_success_at)", () => {
    const qs = buildListQuery({
      pagination: { pageIndex: 0, pageSize: 10 },
      sort: null,
      filters: { last_success_at: { from: "2024-01-01", to: "2024-12-31" } },
    });
    expect(qs).not.toContain("last_success_at");
  });
});

describe("listCompanies", () => {
  it("monta GET /companies?page=...&page_size=... com Authorization", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        items: [],
        page: 1,
        page_size: 25,
        total: 0,
      }),
    );

    const result = await listCompanies(
      {
        pagination: { pageIndex: 0, pageSize: 25 },
        sort: null,
        filters: { status: "active" },
      },
      { accessToken: "tok-123" },
    );

    expect(result).toEqual({ rows: [], total: 0 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain("/companies?");
    expect(String(url)).toContain("page=1");
    expect(String(url)).toContain("page_size=25");
    expect(String(url)).toContain("status=active");
    const headers = new Headers((init as RequestInit).headers);
    expect(headers.get("Authorization")).toBe("Bearer tok-123");
  });

  it("propaga ApiError em status nao-OK", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response("forbidden", { status: 403 }),
    );
    await expect(
      listCompanies(
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

describe("getCompany", () => {
  it("faz GET /companies/{id} e devolve a entidade", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        id: "11111111-1111-1111-1111-111111111111",
        tenant_id: "00000000-0000-0000-0000-000000000000",
        cnpj: "11222333000181",
        razao_social: "Acme",
        nome_fantasia: null,
        municipio_ibge: "3550308",
        uf: "SP",
        status: "active",
        last_nsu: null,
        last_success_at: null,
        portal_provider: null,
        notes: null,
        created_at: "2026-04-15T12:00:00Z",
        updated_at: "2026-04-15T12:00:00Z",
      }),
    );
    const c = await getCompany(
      "11111111-1111-1111-1111-111111111111",
      { accessToken: "x" },
    );
    expect(c.razao_social).toBe("Acme");
    expect(String(fetchMock.mock.calls[0]![0])).toContain(
      "/companies/11111111-1111-1111-1111-111111111111",
    );
  });
});

describe("createCompany", () => {
  it("envia POST /companies com Content-Type JSON e body serializado", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          id: "id-1",
          tenant_id: "t-1",
          cnpj: "11222333000181",
          razao_social: "Acme",
          nome_fantasia: null,
          municipio_ibge: "3550308",
          uf: "SP",
          status: "active",
          last_nsu: null,
          last_success_at: null,
          portal_provider: null,
          notes: null,
          created_at: "2026-04-16T12:00:00Z",
          updated_at: "2026-04-16T12:00:00Z",
        },
        { status: 201 },
      ),
    );
    const c = await createCompany(
      {
        cnpj: "11222333000181",
        razao_social: "Acme",
        municipio_ibge: "3550308",
        uf: "SP",
      },
      { accessToken: "x" },
    );
    expect(c.id).toBe("id-1");
    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect(init.method).toBe("POST");
    const headers = new Headers(init.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(JSON.parse(init.body as string)).toMatchObject({
      cnpj: "11222333000181",
      razao_social: "Acme",
      municipio_ibge: "3550308",
      uf: "SP",
    });
  });
});

describe("updateCompany", () => {
  it("envia PATCH /companies/{id} apenas com campos informados", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        id: "id-1",
        tenant_id: "t-1",
        cnpj: "11222333000181",
        razao_social: "Acme 2",
        nome_fantasia: null,
        municipio_ibge: "3550308",
        uf: "SP",
        status: "paused",
        last_nsu: null,
        last_success_at: null,
        portal_provider: null,
        notes: null,
        created_at: "2026-04-16T12:00:00Z",
        updated_at: "2026-04-16T12:30:00Z",
      }),
    );
    await updateCompany(
      "id-1",
      { razao_social: "Acme 2", status: "paused" },
      { accessToken: "x" },
    );
    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({
      razao_social: "Acme 2",
      status: "paused",
    });
  });
});

describe("deleteCompany", () => {
  it("envia DELETE e nao lanca em 204", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(
      deleteCompany("id-1", { accessToken: "x" }),
    ).resolves.toBeUndefined();
    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect(init.method).toBe("DELETE");
  });

  it("lanca ApiError em 404", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response('{"detail":"company nao encontrada"}', {
        status: 404,
        headers: { "content-type": "application/json" },
      }),
    );
    await expect(
      deleteCompany("id-1", { accessToken: "x" }),
    ).rejects.toMatchObject({ status: 404 });
  });
});

describe("formatCnpj", () => {
  it("formata 14 digitos no padrao mascara", () => {
    expect(formatCnpj("11222333000181")).toBe("11.222.333/0001-81");
  });
  it("devolve raw se nao tiver 14 digitos", () => {
    expect(formatCnpj("123")).toBe("123");
  });
});
