import { describe, expect, it } from "vitest";

import {
  builderToCron,
  computeNextRuns,
  CronParseError,
  cronToBuilder,
  humanizeCron,
  normalizeCronExpr,
  parseCron,
  parseField,
  validateCron,
} from "./cron";

describe("parseField", () => {
  it("parses wildcard with full range", () => {
    const f = parseField("*", [0, 59], "minuto");
    expect(f.isWildcard).toBe(true);
    expect(f.values).toHaveLength(60);
    expect(f.values[0]).toBe(0);
    expect(f.values[59]).toBe(59);
  });

  it("parses comma list", () => {
    const f = parseField("1,5,10", [0, 59], "minuto");
    expect(f.values).toEqual([1, 5, 10]);
    expect(f.isWildcard).toBe(false);
  });

  it("parses range", () => {
    const f = parseField("9-12", [0, 23], "hora");
    expect(f.values).toEqual([9, 10, 11, 12]);
  });

  it("parses step on wildcard", () => {
    const f = parseField("*/15", [0, 59], "minuto");
    expect(f.values).toEqual([0, 15, 30, 45]);
  });

  it("rejects out of range", () => {
    expect(() => parseField("60", [0, 59], "minuto")).toThrow(CronParseError);
  });

  it("rejects reversed range", () => {
    expect(() => parseField("5-3", [0, 59], "minuto")).toThrow(CronParseError);
  });
});

describe("parseCron", () => {
  it("parses 5-field cron normalizing whitespace", () => {
    const p = parseCron("  0  3 *  *  *  ");
    expect(p.expr).toBe("0 3 * * *");
    expect(p.minute.values).toEqual([0]);
    expect(p.hour.values).toEqual([3]);
    expect(p.day.isWildcard).toBe(true);
    expect(p.month.isWildcard).toBe(true);
    expect(p.dow.isWildcard).toBe(true);
  });

  it("rejects non-5-field", () => {
    expect(() => parseCron("0 3 * *")).toThrow(CronParseError);
    expect(() => parseCron("0 3 * * * 2020")).toThrow(CronParseError);
  });

  it("rejects empty", () => {
    expect(() => parseCron("")).toThrow(CronParseError);
  });

  it("accepts presets from the backend", () => {
    expect(() => parseCron("0 3 * * *")).not.toThrow();
    expect(() => parseCron("0 6 * * 1")).not.toThrow();
    expect(() => parseCron("0 5 1 * *")).not.toThrow();
  });
});

describe("validateCron", () => {
  it("returns null on valid", () => {
    expect(validateCron("0 3 * * *")).toBeNull();
  });
  it("returns error message on invalid", () => {
    const err = validateCron("0 25 * * *");
    expect(err).toContain("hora");
  });
});

describe("normalizeCronExpr", () => {
  it("collapses whitespace", () => {
    expect(normalizeCronExpr("  0   3 * *\t*  ")).toBe("0 3 * * *");
  });
});

describe("humanizeCron", () => {
  it("handles daily preset", () => {
    expect(humanizeCron("0 3 * * *")).toBe("Todo dia as 03:00");
  });
  it("handles weekly preset", () => {
    expect(humanizeCron("0 6 * * 1")).toBe("Toda segunda-feira as 06:00");
  });
  it("handles monthly preset", () => {
    expect(humanizeCron("0 5 1 * *")).toBe("Todo mes no dia 1 as 05:00");
  });
  it("handles minute only", () => {
    expect(humanizeCron("30 9 * * *")).toBe("Todo dia as 09:30");
  });
  it("falls back to custom for unsupported forms", () => {
    expect(humanizeCron("*/15 * * * *")).toMatch(/^Cron customizado/);
  });
  it("falls back to custom for invalid", () => {
    expect(humanizeCron("garbage")).toBe("Cron customizado: garbage");
  });
  it("handles a cada minuto", () => {
    expect(humanizeCron("* * * * *")).toBe("A cada minuto");
  });
});

describe("computeNextRuns", () => {
  it("computes next 5 runs for daily cron in UTC", () => {
    const base = new Date(Date.UTC(2026, 0, 1, 0, 0, 0)); // 2026-01-01 00:00 UTC
    const runs = computeNextRuns("0 3 * * *", "UTC", 5, base);
    expect(runs).toHaveLength(5);
    // 03:00 UTC every day starting Jan 1.
    for (let i = 0; i < 5; i += 1) {
      expect(runs[i].getUTCHours()).toBe(3);
      expect(runs[i].getUTCMinutes()).toBe(0);
      expect(runs[i].getUTCDate()).toBe(i + 1);
    }
  });

  it("respects timezone in computing local hour", () => {
    // "0 3 * * *" in America/Sao_Paulo (UTC-3 without DST in 2026)
    // should run at 06:00 UTC.
    const base = new Date(Date.UTC(2026, 0, 1, 0, 0, 0));
    const runs = computeNextRuns("0 3 * * *", "America/Sao_Paulo", 1, base);
    expect(runs).toHaveLength(1);
    expect(runs[0].getUTCHours()).toBe(6);
    expect(runs[0].getUTCMinutes()).toBe(0);
  });

  it("handles weekly cron picking the right weekday", () => {
    // 2026-01-05 is a Monday. `0 6 * * 1` at UTC -> next match should be 2026-01-05 06:00 UTC.
    const base = new Date(Date.UTC(2026, 0, 1, 0, 0, 0)); // Thursday
    const runs = computeNextRuns("0 6 * * 1", "UTC", 3, base);
    expect(runs).toHaveLength(3);
    expect(runs[0].toISOString()).toBe("2026-01-05T06:00:00.000Z");
    expect(runs[1].toISOString()).toBe("2026-01-12T06:00:00.000Z");
    expect(runs[2].toISOString()).toBe("2026-01-19T06:00:00.000Z");
  });

  it("returns empty for invalid cron", () => {
    expect(computeNextRuns("garbage", "UTC", 5)).toEqual([]);
  });

  it("returns empty for invalid timezone", () => {
    expect(computeNextRuns("0 3 * * *", "Mars/Olympus", 5)).toEqual([]);
  });

  it("advances past the base minute", () => {
    // Starting exactly at 03:00, next should be tomorrow 03:00 (not the same).
    const base = new Date(Date.UTC(2026, 0, 1, 3, 0, 0));
    const runs = computeNextRuns("0 3 * * *", "UTC", 1, base);
    expect(runs[0].toISOString()).toBe("2026-01-02T03:00:00.000Z");
  });
});

describe("builderToCron", () => {
  it("builds daily", () => {
    expect(builderToCron({ mode: "daily", hour: 3, minute: 0 })).toBe(
      "0 3 * * *",
    );
  });
  it("builds weekly", () => {
    expect(
      builderToCron({ mode: "weekly", dow: 1, hour: 6, minute: 0 }),
    ).toBe("0 6 * * 1");
  });
  it("builds monthly", () => {
    expect(
      builderToCron({ mode: "monthly", day: 1, hour: 5, minute: 0 }),
    ).toBe("0 5 1 * *");
  });
  it("passes through custom", () => {
    expect(builderToCron({ mode: "custom", expr: "*/15 * * * *" })).toBe(
      "*/15 * * * *",
    );
  });
  it("rejects invalid range", () => {
    expect(() =>
      builderToCron({ mode: "daily", hour: 25, minute: 0 }),
    ).toThrow(CronParseError);
  });
});

describe("cronToBuilder", () => {
  it("recognizes daily", () => {
    expect(cronToBuilder("0 3 * * *")).toEqual({
      mode: "daily",
      hour: 3,
      minute: 0,
    });
  });
  it("recognizes weekly", () => {
    expect(cronToBuilder("0 6 * * 1")).toEqual({
      mode: "weekly",
      dow: 1,
      hour: 6,
      minute: 0,
    });
  });
  it("recognizes monthly", () => {
    expect(cronToBuilder("0 5 1 * *")).toEqual({
      mode: "monthly",
      day: 1,
      hour: 5,
      minute: 0,
    });
  });
  it("falls back to custom", () => {
    expect(cronToBuilder("*/15 * * * *")).toEqual({
      mode: "custom",
      expr: "*/15 * * * *",
    });
  });
});
