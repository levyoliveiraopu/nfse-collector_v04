/**
 * Helpers de periodo (DS-07 PeriodPicker).
 *
 * Trabalhamos com datas *wall-clock* (`YYYY-MM-DD`) em UTC ao usar objetos
 * `Date` como "meio-dia UTC do dia" — evita o off-by-one classico quando
 * o navegador interpreta a string ISO com offset local.
 */

export type PeriodPreset =
  | "current_month"
  | "previous_month"
  | "last_7d"
  | "last_30d"
  | "custom";

export interface PeriodRange {
  from: string; // YYYY-MM-DD
  to: string; // YYYY-MM-DD
  preset: PeriodPreset;
}

export function formatISODate(date: Date): string {
  const yyyy = date.getUTCFullYear();
  const mm = String(date.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(date.getUTCDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function utcDay(year: number, month: number, day: number): Date {
  // Ancorar em 12:00 UTC evita que renderizacoes com fuso negativo
  // caiam no dia anterior.
  return new Date(Date.UTC(year, month, day, 12, 0, 0, 0));
}

/**
 * Calcula o range `{from,to}` de um preset com base em `today`
 * (default: data corrente). `today` e tratado em UTC.
 */
export function computePresetRange(
  preset: Exclude<PeriodPreset, "custom">,
  today: Date = new Date(),
): PeriodRange {
  const y = today.getUTCFullYear();
  const m = today.getUTCMonth();
  const d = today.getUTCDate();
  const todayUtc = utcDay(y, m, d);

  switch (preset) {
    case "current_month": {
      const first = utcDay(y, m, 1);
      return {
        from: formatISODate(first),
        to: formatISODate(todayUtc),
        preset,
      };
    }
    case "previous_month": {
      const first = utcDay(y, m - 1, 1);
      const last = utcDay(y, m, 0); // dia 0 do mes atual = ultimo dia do anterior
      return {
        from: formatISODate(first),
        to: formatISODate(last),
        preset,
      };
    }
    case "last_7d": {
      const from = utcDay(y, m, d - 6); // 7 dias incluindo hoje
      return {
        from: formatISODate(from),
        to: formatISODate(todayUtc),
        preset,
      };
    }
    case "last_30d": {
      const from = utcDay(y, m, d - 29); // 30 dias incluindo hoje
      return {
        from: formatISODate(from),
        to: formatISODate(todayUtc),
        preset,
      };
    }
  }
}

/** Valida uma string `YYYY-MM-DD`. Rejeita datas impossiveis (ex.: 2025-02-30). */
export function isValidISODate(value: string): boolean {
  if (typeof value !== "string") return false;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [y, m, d] = value.split("-").map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  return (
    date.getUTCFullYear() === y &&
    date.getUTCMonth() === m - 1 &&
    date.getUTCDate() === d
  );
}

/** True se `from <= to` (comparando strings `YYYY-MM-DD` lexicograficamente). */
export function isOrderedRange(from: string, to: string): boolean {
  return isValidISODate(from) && isValidISODate(to) && from <= to;
}

export const PRESET_LABELS: Record<Exclude<PeriodPreset, "custom">, string> = {
  current_month: "Mes atual",
  previous_month: "Mes anterior",
  last_7d: "Ultimos 7 dias",
  last_30d: "Ultimos 30 dias",
};
