import { AppShell } from "@/components/app-shell/app-shell";
import { RequireAuth } from "@/components/auth/require-auth";

/**
 * Layout protegido de `/agendamentos/*` (APP-07).
 * Mesmo padrao de `/empresas` e `/usuarios`: guard de sessao + shell.
 */
export default function AgendamentosLayout({
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
