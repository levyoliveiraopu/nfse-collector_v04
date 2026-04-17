/**
 * Catalogo de codigos de ocorrencia no frontend (APP-06).
 *
 * Espelha `docs/architecture/occurrence-codes.md` — manter em sincronia
 * ao adicionar codigos novos. Codigos nao mapeados caem no fallback
 * `"Outro"` sem quebrar a listagem.
 */
import type { OccurrenceSeverity } from "@/lib/api/occurrences";

export type RunbookSlug =
  | "credencial-invalida"
  | "portal-indisponivel"
  | "reprocessamento"
  | "parse-error"
  | "storage-error"
  | "erro-desconhecido";

export interface OccurrenceCodeInfo {
  label: string;
  severity_default: OccurrenceSeverity;
  runbookSlug: RunbookSlug;
}

export const OCCURRENCE_CODES: Record<string, OccurrenceCodeInfo> = {
  CERT_EXPIRED: {
    label: "Certificado expirado",
    severity_default: "error",
    runbookSlug: "credencial-invalida",
  },
  CERT_EXPIRING: {
    label: "Certificado proximo do vencimento",
    severity_default: "warning",
    runbookSlug: "credencial-invalida",
  },
  CERT_REVOKED: {
    label: "Certificado revogado",
    severity_default: "error",
    runbookSlug: "credencial-invalida",
  },
  CRED_INVALID: {
    label: "Credencial invalida",
    severity_default: "error",
    runbookSlug: "credencial-invalida",
  },
  PORTAL_5XX: {
    label: "Portal da prefeitura com falha 5xx",
    severity_default: "error",
    runbookSlug: "portal-indisponivel",
  },
  PORTAL_TIMEOUT: {
    label: "Timeout no portal da prefeitura",
    severity_default: "warning",
    runbookSlug: "portal-indisponivel",
  },
  RATE_LIMIT: {
    label: "Limite de requisicoes atingido",
    severity_default: "warning",
    runbookSlug: "portal-indisponivel",
  },
  REPROCESS_NEEDED: {
    label: "Reprocessamento necessario",
    severity_default: "info",
    runbookSlug: "reprocessamento",
  },
  PARSE_ERROR: {
    label: "Erro ao interpretar retorno",
    severity_default: "error",
    runbookSlug: "parse-error",
  },
  STORAGE_ERROR: {
    label: "Falha de storage",
    severity_default: "critical",
    runbookSlug: "storage-error",
  },
  UNKNOWN: {
    label: "Erro desconhecido",
    severity_default: "error",
    runbookSlug: "erro-desconhecido",
  },
};

export function getCodeInfo(code: string): OccurrenceCodeInfo | null {
  return OCCURRENCE_CODES[code] ?? null;
}

export function codeLabel(code: string): string {
  return getCodeInfo(code)?.label ?? "Outro";
}

export const RUNBOOK_SLUGS: readonly RunbookSlug[] = [
  "credencial-invalida",
  "portal-indisponivel",
  "reprocessamento",
  "parse-error",
  "storage-error",
  "erro-desconhecido",
];

export function isRunbookSlug(value: string): value is RunbookSlug {
  return (RUNBOOK_SLUGS as readonly string[]).includes(value);
}
