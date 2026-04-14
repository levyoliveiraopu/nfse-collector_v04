"use client";

import { useCallback, useState } from "react";
import { cn } from "@/lib/utils";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

type AppShellProps = {
  children: React.ReactNode;
};

/**
 * Shell reutilizavel de paginas logadas. Integra:
 * - Sidebar colapsavel em desktop (256px <-> 64px) e drawer em mobile (<1024px).
 * - Topbar fixa com breadcrumbs, tenant switcher, bell de notificacoes,
 *   theme toggle e user menu.
 * - Landmarks ARIA (aside/header/main/nav) e skip-link para conteudo principal.
 */
export function AppShell({ children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleToggleCollapsed = useCallback(
    () => setCollapsed((value) => !value),
    [],
  );
  const handleOpenMobile = useCallback(() => setMobileOpen(true), []);
  const handleCloseMobile = useCallback(() => setMobileOpen(false), []);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground focus:shadow-md"
      >
        Pular para o conteudo
      </a>

      <Sidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onCloseMobile={handleCloseMobile}
      />

      <div
        className={cn(
          "flex min-h-screen flex-col transition-[padding] duration-200 ease-out",
          collapsed ? "lg:pl-16" : "lg:pl-64",
        )}
      >
        <Topbar
          collapsed={collapsed}
          onToggleCollapsed={handleToggleCollapsed}
          onOpenMobile={handleOpenMobile}
        />

        <main
          id="main-content"
          tabIndex={-1}
          className="flex-1 p-4 focus-visible:outline-none md:p-6 lg:p-8"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
