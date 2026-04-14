import type { ReactNode } from "react";

/**
 * Layout publico para o grupo `(auth)`. Fica sem sidebar/topbar; cada pagina
 * renderiza o proprio `<AuthShell>` via componentes compartilhados.
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
