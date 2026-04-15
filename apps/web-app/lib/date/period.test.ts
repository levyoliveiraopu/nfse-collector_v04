import { describe, expect, it } from "vitest";

import {
  computePresetRange,
  formatISODate,
  isOrderedRange,
  isValidISODate,
} from "./period";

function utc(year: number, month: number, day: number): Date {
  return new Date(Date.UTC(year, month - 1, day, 12, 0, 0, 0));
}

describe("formatISODate", () => {
  it("formata em YYYY-MM-DD em UTC", () => {
    expect(formatISODate(utc(2026, 4, 15))).toBe("2026-04-15");
    expect(formatISODate(utc(2026, 1, 1))).toBe("2026-01-01");
  });
});

describe("computePresetRange", () => {
  // Ancora: 15/abr/2026 (uma quarta-feira).
  const today = utc(2026, 4, 15);

  it("current_month: 1o do mes ate hoje", () => {
    expect(computePresetRange("current_month", today)).toEqual({
      from: "2026-04-01",
      to: "2026-04-15",
      preset: "current_month",
    });
  });

  it("previous_month: 1o ate ultimo dia do mes anterior", () => {
    expect(computePresetRange("previous_month", today)).toEqual({
      from: "2026-03-01",
      to: "2026-03-31",
      preset: "previous_month",
    });
  });

  it("last_7d: 7 dias incluindo hoje", () => {
    expect(computePresetRange("last_7d", today)).toEqual({
      from: "2026-04-09",
      to: "2026-04-15",
      preset: "last_7d",
    });
  });

  it("last_30d: 30 dias incluindo hoje", () => {
    expect(computePresetRange("last_30d", today)).toEqual({
      from: "2026-03-17",
      to: "2026-04-15",
      preset: "last_30d",
    });
  });

  it("previous_month lida com virada de ano", () => {
    expect(computePresetRange("previous_month", utc(2026, 1, 10))).toEqual({
      from: "2025-12-01",
      to: "2025-12-31",
      preset: "previous_month",
    });
  });

  it("previous_month lida com fevereiro em ano bissexto", () => {
    expect(computePresetRange("previous_month", utc(2024, 3, 5))).toEqual({
      from: "2024-02-01",
      to: "2024-02-29",
      preset: "previous_month",
    });
  });
});

describe("isValidISODate", () => {
  it("aceita datas reais", () => {
    expect(isValidISODate("2026-04-15")).toBe(true);
    expect(isValidISODate("2024-02-29")).toBe(true);
  });

  it("rejeita datas impossiveis ou mal formatadas", () => {
    expect(isValidISODate("2025-02-30")).toBe(false);
    expect(isValidISODate("abc")).toBe(false);
    expect(isValidISODate("2026-4-15")).toBe(false);
    expect(isValidISODate("")).toBe(false);
  });
});

describe("isOrderedRange", () => {
  it("true quando from <= to", () => {
    expect(isOrderedRange("2026-04-01", "2026-04-15")).toBe(true);
    expect(isOrderedRange("2026-04-15", "2026-04-15")).toBe(true);
  });

  it("false quando from > to ou datas invalidas", () => {
    expect(isOrderedRange("2026-04-16", "2026-04-15")).toBe(false);
    expect(isOrderedRange("bad", "2026-04-15")).toBe(false);
  });
});
