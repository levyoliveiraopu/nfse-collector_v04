import { describe, expect, it } from "vitest";

import { buildCsv, escapeCsvCell } from "./csv";

describe("escapeCsvCell", () => {
  it("retorna string vazia para null/undefined", () => {
    expect(escapeCsvCell(null)).toBe("");
    expect(escapeCsvCell(undefined)).toBe("");
  });

  it("nao altera strings simples", () => {
    expect(escapeCsvCell("abc")).toBe("abc");
    expect(escapeCsvCell(42)).toBe("42");
  });

  it("envolve e escapa aspas", () => {
    expect(escapeCsvCell('ele disse "oi"')).toBe('"ele disse ""oi"""');
  });

  it("envolve quando contem virgula", () => {
    expect(escapeCsvCell("a,b")).toBe('"a,b"');
  });

  it("envolve quando contem quebra de linha", () => {
    expect(escapeCsvCell("linha1\nlinha2")).toBe('"linha1\nlinha2"');
    expect(escapeCsvCell("linha1\r\nlinha2")).toBe('"linha1\r\nlinha2"');
  });

  it("serializa Date como ISO", () => {
    const d = new Date("2026-04-14T10:00:00.000Z");
    expect(escapeCsvCell(d)).toBe("2026-04-14T10:00:00.000Z");
  });
});

describe("buildCsv", () => {
  it("monta header + linhas", () => {
    const rows = [
      { id: 1, name: "Alice" },
      { id: 2, name: "Bob" },
    ];
    const csv = buildCsv(rows, [
      { key: "id", header: "ID" },
      { key: "name", header: "Nome" },
    ]);
    expect(csv).toBe("ID,Nome\r\n1,Alice\r\n2,Bob");
  });

  it("usa getValue quando fornecido", () => {
    const rows = [{ a: 10, b: 20 }];
    const csv = buildCsv(rows, [
      { key: "soma", header: "Soma", getValue: (r) => r.a + r.b },
    ]);
    expect(csv).toBe("Soma\r\n30");
  });

  it("retorna apenas header quando rows vazio", () => {
    expect(buildCsv([], [{ key: "x", header: "X" }])).toBe("X");
  });

  it("escapa celulas com caracteres especiais", () => {
    const rows = [{ nome: 'Ltda, "ABC"' }];
    const csv = buildCsv(rows, [{ key: "nome", header: "Nome" }]);
    expect(csv).toBe('Nome\r\n"Ltda, ""ABC"""');
  });
});
