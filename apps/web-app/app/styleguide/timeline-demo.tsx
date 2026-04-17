import { Timeline, type TimelineItem } from "@/components/ui/timeline";

const ITEMS: TimelineItem[] = [
  {
    id: "1",
    timestamp: "2026-04-17T09:00:00-03:00",
    title: "Execucao agendada iniciada",
    description: "Tenant acme, empresa ACME Comercio LTDA.",
    tone: "info",
  },
  {
    id: "2",
    timestamp: "2026-04-17T09:02:14-03:00",
    title: "Autenticado no portal",
    description: "Certificado A1 valido ate 2026-11-02.",
    tone: "default",
  },
  {
    id: "3",
    timestamp: "2026-04-17T09:04:48-03:00",
    title: "158 NFS-e coletadas",
    tone: "success",
  },
  {
    id: "4",
    timestamp: "2026-04-17T09:05:02-03:00",
    title: "XLSX gerado e enviado para o bucket",
    description: "s3://nfse-saas-prod/tenants-exports/acme/2026-04-17.xlsx",
    tone: "success",
  },
  {
    id: "5",
    timestamp: "2026-04-17T09:05:03-03:00",
    title: "Falha parcial: PORTAL_TIMEOUT",
    description: "3 notas reenfileiradas para o proximo ciclo.",
    tone: "warning",
  },
];

export function TimelineDemo() {
  return (
    <div className="rounded-lg border border-border bg-card p-6">
      <Timeline items={ITEMS} ariaLabel="Execucao 2026-04-17 09:00" />
    </div>
  );
}
