"use client";

import { OcorrenciasTable } from "./ocorrencias-table";

/**
 * View client do inbox `/ocorrencias` (APP-06).
 *
 * A API-09 ja expoe `GET /occurrences` com filtros `status`/`severity`/
 * `company_id`. Esta view encapsula apenas a tabela — as acoes
 * (acknowledge/resolve/assign) vivem no detalhe para evitar confusao de
 * bulk-actions nesta entrega.
 */
export function OcorrenciasView() {
  return (
    <div data-view="ocorrencias">
      <OcorrenciasTable />
    </div>
  );
}
