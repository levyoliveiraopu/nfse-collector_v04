import { AppShell } from "@/components/app-shell/app-shell";
import { RequireAuth } from "@/components/auth/require-auth";

export default function AjudaLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <AppShell>{children}</AppShell>
    </RequireAuth>
  );
}
