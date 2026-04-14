import type { FilterState, SavedFilter, SortState } from "./types";

/**
 * Persistencia de filtros salvos em `localStorage`. Uma chave por tabela
 * (ex.: `dt:executions`). Armazena um array de `SavedFilter`.
 */

export function listSavedFilters(storageKey: string): SavedFilter[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SavedFilter[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveFilter(
  storageKey: string,
  name: string,
  filters: FilterState,
  sort: SortState | null,
): SavedFilter {
  const existing = listSavedFilters(storageKey);
  const entry: SavedFilter = {
    id:
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `sf_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    name,
    filters,
    sort,
    createdAt: new Date().toISOString(),
  };
  const next = [entry, ...existing.filter((e) => e.name !== name)].slice(0, 20);
  window.localStorage.setItem(storageKey, JSON.stringify(next));
  return entry;
}

export function deleteSavedFilter(storageKey: string, id: string): void {
  if (typeof window === "undefined") return;
  const next = listSavedFilters(storageKey).filter((e) => e.id !== id);
  window.localStorage.setItem(storageKey, JSON.stringify(next));
}
