import { AppShell } from "@/components/app-shell/app-shell";
import { RequireAuth } from "@/components/auth/require-auth";

/**
 * Layout protegido da rota `/ocorrencias/*` (APP-06). Mesmo guard +
 * shell usado em `/empresas` e `/usuarios`.
 */
export default function OcorrenciasLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RequireAuth>
      <AppShell>{children}</AppShell>
    </RequireAuth>
  );
}
