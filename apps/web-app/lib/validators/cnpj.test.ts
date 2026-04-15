import { describe, expect, it } from "vitest";

import { formatCnpj, isValidCnpj, normalizeCnpj } from "./cnpj";

// CNPJs publicos com DV real — mesmos casos de `apps/api/tests/test_companies_cnpj.py`.
const VALID_CNPJS = [
  "00000000000191", // Banco do Brasil
  "33000167000101", // Petrobras
  "60746948000112", // Bradesco
];

const INVALID_DV = [
  "00000000000190",
  "33000167000102",
  "60746948000111",
];

const REPEATED = [
  "00000000000000",
  "11111111111111",
  "99999999999999",
];

describe("normalizeCnpj", () => {
  it("remove pontos, barra e traco", () => {
    expect(normalizeCnpj("00.000.000/0001-91")).toBe("00000000000191");
  });

  it("retorna vazio para null/undefined", () => {
    expect(normalizeCnpj(null)).toBe("");
    expect(normalizeCnpj(undefined)).toBe("");
  });

  it("preserva somente digitos mesmo com ruido", () => {
    expect(normalizeCnpj("abc00.000.000/0001-91xyz")).toBe("00000000000191");
  });
});

describe("isValidCnpj", () => {
  it.each(VALID_CNPJS)("aceita CNPJ publico valido: %s", (cnpj) => {
    expect(isValidCnpj(cnpj)).toBe(true);
  });

  it.each(INVALID_DV)("rejeita DV incorreto: %s", (cnpj) => {
    expect(isValidCnpj(cnpj)).toBe(false);
  });

  it.each(REPEATED)("rejeita sequencia repetida: %s", (cnpj) => {
    expect(isValidCnpj(cnpj)).toBe(false);
  });

  it("rejeita comprimento diferente de 14", () => {
    expect(isValidCnpj("123")).toBe(false);
    expect(isValidCnpj("000000000001911")).toBe(false);
  });

  it("rejeita string com caracteres nao-digito", () => {
    expect(isValidCnpj("00.000.000/0001-91")).toBe(false);
  });
});

describe("formatCnpj", () => {
  it.each([
    ["", ""],
    ["0", "0"],
    ["00", "00"],
    ["000", "00.0"],
    ["00000", "00.000"],
    ["000000", "00.000.0"],
    ["00000000", "00.000.000"],
    ["000000000", "00.000.000/0"],
    ["000000000001", "00.000.000/0001"],
    ["00000000000191", "00.000.000/0001-91"],
  ])("formata %s -> %s", (input, expected) => {
    expect(formatCnpj(input)).toBe(expected);
  });

  it("trunca em 14 digitos", () => {
    expect(formatCnpj("000000000001910000")).toBe("00.000.000/0001-91");
  });

  it("aceita input ja formatado (idempotente)", () => {
    expect(formatCnpj("00.000.000/0001-91")).toBe("00.000.000/0001-91");
  });
});
