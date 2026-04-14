/**
 * Geracao de CSV (RFC 4180) a partir do resultado visivel da DataTable.
 * Lida com escape de virgulas, aspas duplas e quebras de linha, e aplica
 * BOM UTF-8 para compatibilidade com Excel em portugues.
 */

export interface CsvColumn<T> {
  /** Chave usada como accessor. Se `getValue` for passado, prevalece. */
  key: string;
  /** Cabecalho na primeira linha do CSV. */
  header: string;
  /** Extrator opcional. Default: `row[key]`. */
  getValue?: (row: T) => unknown;
}

const SEP = ",";
const EOL = "\r\n";
const BOM = "\uFEFF";

export function escapeCsvCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const str = value instanceof Date ? value.toISOString() : String(value);
  if (/[",\r\n]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export function buildCsv<T>(rows: T[], columns: CsvColumn<T>[]): string {
  const header = columns.map((c) => escapeCsvCell(c.header)).join(SEP);
  const body = rows
    .map((row) =>
      columns
        .map((c) => {
          const raw = c.getValue
            ? c.getValue(row)
            : (row as Record<string, unknown>)[c.key];
          return escapeCsvCell(raw);
        })
        .join(SEP),
    )
    .join(EOL);
  return body.length > 0 ? `${header}${EOL}${body}` : header;
}

/**
 * Dispara download do CSV no browser. Seguro para chamar no client apenas.
 * Retorna `false` se `window` nao estiver disponivel.
 */
export function downloadCsv(
  filename: string,
  csv: string,
  options: { bom?: boolean } = {},
): boolean {
  if (typeof window === "undefined") return false;
  const withBom = options.bom !== false;
  const blob = new Blob([withBom ? BOM + csv : csv], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  return true;
}
