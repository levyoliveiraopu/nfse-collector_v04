import { LayoutDashboard } from "lucide-react";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <LayoutDashboard className="h-12 w-12 text-primary" aria-hidden="true" />
      <h1 className="text-3xl font-semibold tracking-tight">Hello painel</h1>
      <p className="text-sm text-muted-foreground">
        Painel NFS-e SaaS — bootstrap inicial (DS-01).
      </p>
    </main>
  );
}
