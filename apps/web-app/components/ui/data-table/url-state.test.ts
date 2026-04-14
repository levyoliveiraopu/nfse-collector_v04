import { describe, expect, it } from "vitest";

import type { FilterSchema } from "./types";
import {
  parseState,
  serializeState,
  stripDataTableParams,
} from "./url-state";

const schema: FilterSchema[] = [
  { kind: "text", key: "q", label: "Buscar" },
  {
    kind: "select",
    key: "status",
    label: "Status",
    options: [
      { value: "success", label: "Sucesso" },
      { value: "failed", label: "Falhou" },
    ],
  },
  { kind: "date-range", key: "periodo", label: "Periodo" },
];

describe("serializeState", () => {
  it("omite defaults (page 1 e pageSize default)", () => {
    const out = serializeState(
      {
        pagination: { pageIndex: 0, pageSize: 25 },
        sort: null,
        filters: {},
      },
      schema,
      { defaultPageSize: 25 },
    );
    expect(out.toString()).toBe("");
  });

  it("serializa page 1-based + size nao-default", () => {
    const out = serializeState(
      {
        pagination: { pageIndex: 2, pageSize: 50 },
        sort: null,
        filters: {},
      },
      schema,
      { defaultPageSize: 25 },
    );
    expect(out.get("page")).toBe("3");
    expect(out.get("size")).toBe("50");
  });

  it("serializa sort asc/desc", () => {
    const asc = serializeState(
      {
        pagination: { pageIndex: 0, pageSize: 25 },
        sort: { id: "razao_social", desc: false },
        filters: {},
      },
      schema,
      { defaultPageSize: 25 },
    );
    expect(asc.get("sort")).toBe("razao_social:asc");
    const desc = serializeState(
      {
        pagination: { pageIndex: 0, pageSize: 25 },
        sort: { id: "valor", desc: true },
        filters: {},
      },
      schema,
      { defaultPageSize: 25 },
    );
    expect(desc.get("sort")).toBe("valor:desc");
  });

  it("serializa filtros texto/select/date-range com prefixo", () => {
    const out = serializeState(
      {
        pagination: { pageIndex: 0, pageSize: 25 },
        sort: null,
        filters: {
          q: "acme",
          status: "success",
          periodo: { from: "2026-01-01", to: "2026-03-31" },
        },
      },
      schema,
      { prefix: "dt.", defaultPageSize: 25 },
    );
    expect(out.get("dt.f.q")).toBe("acme");
    expect(out.get("dt.f.status")).toBe("success");
    expect(out.get("dt.f.periodo.from")).toBe("2026-01-01");
    expect(out.get("dt.f.periodo.to")).toBe("2026-03-31");
  });
});

describe("parseState", () => {
  it("usa defaults quando nao ha params", () => {
    const s = parseState(new URLSearchParams(""), schema, {
      defaultPageSize: 25,
    });
    expect(s.pagination).toEqual({ pageIndex: 0, pageSize: 25 });
    expect(s.sort).toBeNull();
    expect(s.filters).toEqual({});
  });

  it("roundtrip de estado complexo preserva valores", () => {
    const initial = {
      pagination: { pageIndex: 4, pageSize: 50 },
      sort: { id: "valor", desc: true },
      filters: {
        q: "ltda",
        status: "success",
        periodo: { from: "2026-01-01", to: "2026-02-01" },
      },
    };
    const sp = serializeState(initial, schema, {
      prefix: "dt.",
      defaultPageSize: 25,
    });
    const parsed = parseState(sp, schema, {
      prefix: "dt.",
      defaultPageSize: 25,
    });
    expect(parsed).toEqual(initial);
  });

  it("ignora page <=0 e size invalido", () => {
    const sp = new URLSearchParams("page=0&size=abc");
    const s = parseState(sp, schema, { defaultPageSize: 25 });
    expect(s.pagination.pageIndex).toBe(0);
    expect(s.pagination.pageSize).toBe(25);
  });
});

describe("stripDataTableParams", () => {
  it("preserva params externos e remove os da tabela", () => {
    const sp = new URLSearchParams(
      "tab=notas&dt.page=2&dt.sort=valor:desc&dt.f.q=x&dt.f.periodo.from=2026-01-01",
    );
    const out = stripDataTableParams(sp, schema, "dt.");
    expect(out.get("tab")).toBe("notas");
    expect(out.has("dt.page")).toBe(false);
    expect(out.has("dt.sort")).toBe(false);
    expect(out.has("dt.f.q")).toBe(false);
    expect(out.has("dt.f.periodo.from")).toBe(false);
  });
});
