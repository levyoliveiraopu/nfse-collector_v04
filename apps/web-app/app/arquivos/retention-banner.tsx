import { Clock } from "lucide-react";

/**
 * Banner fixo de retencao — ADR-003 define 90 dias sem arquivamento.
 * DoD do ticket APP-08 exige que esse aviso esteja visivel SEMPRE
 * na pagina `/arquivos`. Nao e descartavel.
 */
export function RetentionBanner() {
  return (
    <div
      role="note"
      aria-label="Politica de retencao de arquivos"
      data-testid="retention-banner"
      className="flex items-start gap-3 rounded-md border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-200"
    >
      <Clock className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div className="flex flex-col gap-0.5">
        <strong className="font-medium">Retencao de 90 dias</strong>
        <span className="text-xs opacity-90">
          Arquivos sao apagados automaticamente 90 dias apos a criacao
          (ADR-003). Exports ZIP tem retencao de 30 dias. Baixe o que
          precisar preservar localmente.
        </span>
      </div>
    </div>
  );
}
