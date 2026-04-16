import { CompanyDetailView } from "./company-detail-view";

export const metadata = {
  title: "Empresa — NFS-e SaaS",
};

export default function CompanyDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return <CompanyDetailView companyId={params.id} />;
}
