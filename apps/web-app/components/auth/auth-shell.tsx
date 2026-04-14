import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

type AuthShellProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
};

/**
 * Wrapper comum das paginas publicas de auth. Coluna centralizada com
 * cartao sobre background de tokens, logo simbolica e rodape opcional
 * com links auxiliares.
 */
export function AuthShell({ title, subtitle, children, footer }: AuthShellProps) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-2 text-primary">
          <ShieldCheck className="h-6 w-6" aria-hidden="true" />
          <span className="text-lg font-semibold tracking-tight">
            NFS-e SaaS
          </span>
        </div>
        <div className="rounded-lg border border-border bg-card p-6 text-card-foreground shadow-sm">
          <header className="mb-6 text-center">
            <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
            {subtitle ? (
              <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>
            ) : null}
          </header>
          {children}
        </div>
        {footer ? (
          <footer className="mt-4 text-center text-xs text-muted-foreground">
            {footer}
          </footer>
        ) : (
          <footer className="mt-4 text-center text-xs text-muted-foreground">
            <Link href="/legal" className="hover:underline">
              Termos e Privacidade
            </Link>
          </footer>
        )}
      </div>
    </main>
  );
}
