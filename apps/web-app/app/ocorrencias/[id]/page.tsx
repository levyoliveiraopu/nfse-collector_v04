import { OccurrenceDetailView } from "./occurrence-detail-view";

export const metadata = {
  title: "Ocorrencia — NFS-e SaaS",
};

export default function OccurrenceDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return <OccurrenceDetailView occurrenceId={params.id} />;
}
