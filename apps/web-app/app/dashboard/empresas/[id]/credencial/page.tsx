import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { CredentialPanel } from "@/components/companies/credential-panel";

/**
 * Rota `/dashboard/empresas/[id]/credencial` (APP-04).
 *
 * Herda `<RequireAuth>` + `<AppShell>` do `dashboard/layout.tsx`. Quando
 * APP-02/APP-03 chegarem, esta pagina vira uma aba dentro do detalhe
 * da empresa; ate la, entramos aqui direto por link/deep-link.
 */
export default function CompanyCredentialPage({
  params,
}: {
  params: { id: string };
}) {
  return (
    <div className="flex flex-col gap-6">
      <nav aria-label="Voltar" className="text-sm text-muted-foreground">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1 hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ChevronLeft aria-hidden="true" className="h-4 w-4" />
          Voltar ao dashboard
        </Link>
      </nav>
      <CredentialPanel companyId={params.id} />
    </div>
  );
}
