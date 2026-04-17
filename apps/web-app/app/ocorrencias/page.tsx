import { OcorrenciasView } from "./ocorrencias-view";

export const metadata = {
  title: "Ocorrencias — NFS-e SaaS",
};

export default function OcorrenciasPage() {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Ocorrencias</h1>
          <p className="text-sm text-muted-foreground">
            Inbox operacional: triagem de incidentes da coleta com runbook
            inline por codigo.
          </p>
        </div>
      </header>

      <OcorrenciasView />
    </div>
  );
}
