import { AppShell } from "@/components/app-shell/app-shell";
import { RequireAuth } from "@/components/auth/require-auth";

/**
 * Layout protegido da rota `/empresas/*` (APP-03). Reusa o mesmo padrao
 * do `/dashboard`: guard de sessao + shell com sidebar/topbar.
 */
export default function EmpresasLayout({
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
