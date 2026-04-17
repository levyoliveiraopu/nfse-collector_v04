/**
 * Helpers puros de cron para a UI de `/agendamentos` (APP-07).
 *
 * Contrato alinhado com o backend (API-12, `apps/api/api/schedules/cron.py`):
 *
 * - Cron **5 campos**: `minuto hora dia-do-mes mes dia-da-semana`.
 * - Valores por campo: minuto 0-59, hora 0-23, dia 1-31, mes 1-12, dow 0-6
 *   (0 = domingo). Sintaxe: `*`, `*\/N`, `a,b,c`, `a-b`, `a-b\/N`.
 * - Nomes (jan/feb/mon/tue/...) **nao** sao suportados aqui — o builder
 *   da UI produz apenas numeros e o backend aceita o subset equivalente.
 *
 * Todas as funcoes sao puras e sem dependencias de runtime Next. O
 * calculo de "proximo run" roda em JS com `Intl.DateTimeFormat` para
 * extrair componentes locais da TZ alvo — evita dep externa de cron.
 */

export const MIN_RANGE: [number, number] = [0, 59];
export const HOUR_RANGE: [number, number] = [0, 23];
export const DAY_RANGE: [number, number] = [1, 31];
export const MONTH_RANGE: [number, number] = [1, 12];
export const DOW_RANGE: [number, number] = [0, 6];

const FIELD_RANGES: [number, number][] = [
  MIN_RANGE,
  HOUR_RANGE,
  DAY_RANGE,
  MONTH_RANGE,
  DOW_RANGE,
];

export const DOW_LABEL_PT: Record<number, string> = {
  0: "domingo",
  1: "segunda-feira",
  2: "terca-feira",
  3: "quarta-feira",
  4: "quinta-feira",
  5: "sexta-feira",
  6: "sabado",
};

export type CronField = {
  /** Conjunto ordenado de valores permitidos no campo. */
  values: number[];
  /** `true` se o campo original era `*` (com ou sem step). */
  isWildcard: boolean;
};

export type ParsedCron = {
  expr: string;
  minute: CronField;
  hour: CronField;
  day: CronField;
  month: CronField;
  dow: CronField;
};

export class CronParseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CronParseError";
  }
}

/**
 * Normaliza uma expressao cron: trim + colapso de espacos repetidos.
 */
export function normalizeCronExpr(expr: string): string {
  return expr.trim().split(/\s+/).join(" ");
}

/**
 * Faz parse de um campo individual (minuto/hora/...). Lanca
 * `CronParseError` com mensagem curta em caso de invalidez.
 */
export function parseField(
  raw: string,
  range: [number, number],
  label: string,
): CronField {
  if (raw.length === 0) {
    throw new CronParseError(`campo ${label} vazio`);
  }
  const parts = raw.split(",");
  const collected = new Set<number>();
  let isWildcard = false;

  for (const part of parts) {
    if (part.length === 0) {
      throw new CronParseError(`campo ${label} com item vazio`);
    }
    // Separa step: "X/N".
    let base = part;
    let step = 1;
    const slashIdx = part.indexOf("/");
    if (slashIdx >= 0) {
      base = part.slice(0, slashIdx);
      const stepRaw = part.slice(slashIdx + 1);
      if (!/^[1-9]\d*$/.test(stepRaw)) {
        throw new CronParseError(
          `step invalido em ${label}: ${part}`,
        );
      }
      step = parseInt(stepRaw, 10);
    }

    let from: number;
    let to: number;
    if (base === "*") {
      from = range[0];
      to = range[1];
      isWildcard = true;
    } else if (base.includes("-")) {
      const [a, b] = base.split("-");
      if (!/^\d+$/.test(a) || !/^\d+$/.test(b)) {
        throw new CronParseError(
          `range invalido em ${label}: ${base}`,
        );
      }
      from = parseInt(a, 10);
      to = parseInt(b, 10);
      if (from > to) {
        throw new CronParseError(
          `range fora de ordem em ${label}: ${base}`,
        );
      }
    } else {
      if (!/^\d+$/.test(base)) {
        throw new CronParseError(
          `valor invalido em ${label}: ${base}`,
        );
      }
      from = parseInt(base, 10);
      to = from;
      if (slashIdx >= 0) {
        // "5/10" significa "a partir de 5 com passo 10" ate o fim do range.
        to = range[1];
      }
    }

    if (from < range[0] || to > range[1]) {
      throw new CronParseError(
        `valor fora do intervalo em ${label} (${range[0]}-${range[1]}): ${part}`,
      );
    }

    for (let v = from; v <= to; v += step) {
      collected.add(v);
    }
  }

  const values = Array.from(collected).sort((a, b) => a - b);
  if (values.length === 0) {
    throw new CronParseError(`campo ${label} sem valores efetivos`);
  }
  return { values, isWildcard };
}

/**
 * Faz parse de uma expressao cron completa de 5 campos.
 * Lanca `CronParseError` com mensagem curta em caso de invalidez.
 */
export function parseCron(expr: string): ParsedCron {
  const normalized = normalizeCronExpr(expr);
  if (normalized.length === 0) {
    throw new CronParseError("expressao vazia");
  }
  const parts = normalized.split(" ");
  if (parts.length !== 5) {
    throw new CronParseError(
      `cron deve ter 5 campos (minuto hora dia mes dow); recebido ${parts.length}`,
    );
  }
  const labels = ["minuto", "hora", "dia", "mes", "dia-da-semana"] as const;
  const [minute, hour, day, month, dow] = parts.map((p, i) =>
    parseField(p, FIELD_RANGES[i], labels[i]),
  );
  return { expr: normalized, minute, hour, day, month, dow };
}

/**
 * Valida uma expressao cron — retorna `null` se ok ou uma mensagem de
 * erro curta (string). Util para form validation.
 */
export function validateCron(expr: string): string | null {
  try {
    parseCron(expr);
    return null;
  } catch (err) {
    if (err instanceof CronParseError) return err.message;
    return "cron invalida";
  }
}

// ---------------------------------------------------------------------------
// Humanizador
// ---------------------------------------------------------------------------

function pad2(n: number): string {
  return n.toString().padStart(2, "0");
}

function allOf(range: [number, number]): number[] {
  const out: number[] = [];
  for (let v = range[0]; v <= range[1]; v += 1) out.push(v);
  return out;
}

function arraysEqual(a: number[], b: number[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) if (a[i] !== b[i]) return false;
  return true;
}

/**
 * Traduz uma expressao cron para uma frase curta em portugues. Cobre as
 * formas produzidas pelo builder amigavel da UI + os presets do backend.
 * Crons fora dessas formas caem em "Cron customizado: <expr>".
 */
export function humanizeCron(expr: string): string {
  const normalized = normalizeCronExpr(expr);
  let parsed: ParsedCron;
  try {
    parsed = parseCron(normalized);
  } catch {
    return `Cron customizado: ${normalized}`;
  }

  const { minute, hour, day, month, dow } = parsed;

  const mAllMinutes = arraysEqual(minute.values, allOf(MIN_RANGE));
  const hAllHours = arraysEqual(hour.values, allOf(HOUR_RANGE));
  const monthAll = arraysEqual(month.values, allOf(MONTH_RANGE));
  const dayAll = arraysEqual(day.values, allOf(DAY_RANGE));
  const dowAll = arraysEqual(dow.values, allOf(DOW_RANGE));

  // Casos degenerados que sao uteis de mostrar sem cair em customizado.
  if (mAllMinutes && hAllHours && monthAll && dayAll && dowAll) {
    return "A cada minuto";
  }

  if (!monthAll) {
    return `Cron customizado: ${normalized}`;
  }

  // Builder so gera crons com um unico minuto e uma unica hora.
  if (minute.values.length !== 1 || hour.values.length !== 1) {
    return `Cron customizado: ${normalized}`;
  }
  const mm = minute.values[0];
  const hh = hour.values[0];
  const time = `${pad2(hh)}:${pad2(mm)}`;

  // "Todo dia as HH:MM" (dia * e dow *).
  if (dayAll && dowAll) {
    return `Todo dia as ${time}`;
  }

  // "Toda <dia da semana> as HH:MM" (dia * e dow unico).
  if (dayAll && dow.values.length === 1) {
    const label = DOW_LABEL_PT[dow.values[0]];
    if (label) {
      return `Toda ${label} as ${time}`;
    }
  }

  // "Todo mes no dia D as HH:MM" (dia unico e dow *).
  if (dowAll && day.values.length === 1) {
    const d = day.values[0];
    return `Todo mes no dia ${d} as ${time}`;
  }

  return `Cron customizado: ${normalized}`;
}

// ---------------------------------------------------------------------------
// Proximos runs
// ---------------------------------------------------------------------------

/**
 * Extrai componentes locais de um `Date` UTC na TZ alvo, usando
 * `Intl.DateTimeFormat` com `timeZone`. Retorna um objeto com campos
 * numericos (evita ambiguidade de `toLocaleString`).
 */
function localParts(
  date: Date,
  timeZone: string,
): {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  dow: number;
} {
  // `en-US` + `formatToParts` produz tokens ASCII estaveis.
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    weekday: "short",
    hour12: false,
  });
  const parts = fmt.formatToParts(date);
  const lookup = new Map<string, string>();
  for (const p of parts) {
    if (p.type !== "literal") lookup.set(p.type, p.value);
  }
  const WEEKDAY_MAP: Record<string, number> = {
    Sun: 0,
    Mon: 1,
    Tue: 2,
    Wed: 3,
    Thu: 4,
    Fri: 5,
    Sat: 6,
  };
  const hourRaw = lookup.get("hour") ?? "00";
  const hourNorm = hourRaw === "24" ? "00" : hourRaw;
  return {
    year: parseInt(lookup.get("year") ?? "0", 10),
    month: parseInt(lookup.get("month") ?? "0", 10),
    day: parseInt(lookup.get("day") ?? "0", 10),
    hour: parseInt(hourNorm, 10),
    minute: parseInt(lookup.get("minute") ?? "0", 10),
    dow: WEEKDAY_MAP[lookup.get("weekday") ?? "Sun"] ?? 0,
  };
}

/**
 * Testa se um instante UTC casa com a expressao cron quando avaliado na
 * TZ alvo. Segue a convencao Unix: dia-do-mes e dia-da-semana sao ORados
 * se ambos sao restritos; se um dos dois e wildcard, so o outro vale.
 */
function matches(
  date: Date,
  parsed: ParsedCron,
  timeZone: string,
): boolean {
  const p = localParts(date, timeZone);
  if (!parsed.minute.values.includes(p.minute)) return false;
  if (!parsed.hour.values.includes(p.hour)) return false;
  if (!parsed.month.values.includes(p.month)) return false;

  const dayMatch = parsed.day.values.includes(p.day);
  const dowMatch = parsed.dow.values.includes(p.dow);
  if (parsed.day.isWildcard && parsed.dow.isWildcard) return true;
  if (parsed.day.isWildcard) return dowMatch;
  if (parsed.dow.isWildcard) return dayMatch;
  // Ambos restritos -> OR.
  return dayMatch || dowMatch;
}

/**
 * Calcula os proximos `count` disparos de uma expressao cron na TZ alvo,
 * a partir de `base` (UTC, default = now).
 *
 * Lookahead maximo: 2 anos (evita loop em crons impossiveis tipo
 * `0 0 31 2 *` — 31 de fevereiro). Em crons legitimos (tudo que o builder
 * produz) a busca termina em no maximo 2 anos. Se nao encontrarmos
 * `count` matches, retornamos os encontrados.
 */
export function computeNextRuns(
  expr: string,
  timeZone: string,
  count = 5,
  base: Date = new Date(),
): Date[] {
  let parsed: ParsedCron;
  try {
    parsed = parseCron(expr);
  } catch {
    return [];
  }

  if (!isValidTimeZone(timeZone)) return [];

  // Zera segundos/ms e avanca para o proximo minuto cheio.
  const start = new Date(base.getTime());
  start.setUTCSeconds(0, 0);
  start.setUTCMinutes(start.getUTCMinutes() + 1);

  const out: Date[] = [];
  // 2 anos em minutos: ~1.052.640. O early-exit acelera casos normais.
  const MAX_MINUTES = 366 * 2 * 24 * 60;
  let cur = start;
  for (let i = 0; i < MAX_MINUTES && out.length < count; i += 1) {
    if (matches(cur, parsed, timeZone)) {
      out.push(new Date(cur.getTime()));
    }
    cur = new Date(cur.getTime() + 60_000);
  }
  return out;
}

export function isValidTimeZone(tz: string): boolean {
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: tz });
    return true;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Builder helpers
// ---------------------------------------------------------------------------

/**
 * Modos do builder amigavel. `custom` aceita cron-expr livre.
 */
export type BuilderMode = "daily" | "weekly" | "monthly" | "custom";

export type BuilderValue =
  | { mode: "daily"; hour: number; minute: number }
  | { mode: "weekly"; dow: number; hour: number; minute: number }
  | { mode: "monthly"; day: number; hour: number; minute: number }
  | { mode: "custom"; expr: string };

/**
 * Converte um valor do builder em uma cron-expr. Lanca `CronParseError`
 * se algum componente estiver fora do range — a UI deve bloquear antes.
 */
export function builderToCron(value: BuilderValue): string {
  switch (value.mode) {
    case "daily": {
      assertRange(value.hour, HOUR_RANGE, "hora");
      assertRange(value.minute, MIN_RANGE, "minuto");
      return `${value.minute} ${value.hour} * * *`;
    }
    case "weekly": {
      assertRange(value.hour, HOUR_RANGE, "hora");
      assertRange(value.minute, MIN_RANGE, "minuto");
      assertRange(value.dow, DOW_RANGE, "dia-da-semana");
      return `${value.minute} ${value.hour} * * ${value.dow}`;
    }
    case "monthly": {
      assertRange(value.hour, HOUR_RANGE, "hora");
      assertRange(value.minute, MIN_RANGE, "minuto");
      assertRange(value.day, DAY_RANGE, "dia");
      return `${value.minute} ${value.hour} ${value.day} * *`;
    }
    case "custom": {
      return normalizeCronExpr(value.expr);
    }
  }
}

function assertRange(
  v: number,
  range: [number, number],
  label: string,
): void {
  if (!Number.isInteger(v) || v < range[0] || v > range[1]) {
    throw new CronParseError(
      `${label} fora do intervalo (${range[0]}-${range[1]}): ${v}`,
    );
  }
}

/**
 * Best-effort: tenta inferir um `BuilderValue` a partir de uma cron-expr
 * existente (para abrir o dialog de edicao no modo certo). Crons fora
 * das formas do builder voltam como `{ mode: "custom" }`.
 */
export function cronToBuilder(expr: string): BuilderValue {
  const normalized = normalizeCronExpr(expr);
  let parsed: ParsedCron;
  try {
    parsed = parseCron(normalized);
  } catch {
    return { mode: "custom", expr: normalized };
  }

  const oneMin = parsed.minute.values.length === 1 ? parsed.minute.values[0] : null;
  const oneHour = parsed.hour.values.length === 1 ? parsed.hour.values[0] : null;
  const monthAll = arraysEqual(parsed.month.values, allOf(MONTH_RANGE));
  const dayAll = arraysEqual(parsed.day.values, allOf(DAY_RANGE));
  const dowAll = arraysEqual(parsed.dow.values, allOf(DOW_RANGE));

  if (oneMin === null || oneHour === null || !monthAll) {
    return { mode: "custom", expr: normalized };
  }

  if (dayAll && dowAll) {
    return { mode: "daily", hour: oneHour, minute: oneMin };
  }
  if (dayAll && parsed.dow.values.length === 1) {
    return {
      mode: "weekly",
      dow: parsed.dow.values[0],
      hour: oneHour,
      minute: oneMin,
    };
  }
  if (dowAll && parsed.day.values.length === 1) {
    return {
      mode: "monthly",
      day: parsed.day.values[0],
      hour: oneHour,
      minute: oneMin,
    };
  }
  return { mode: "custom", expr: normalized };
}
