"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "./nav-items";

type SidebarProps = {
  collapsed: boolean;
  mobileOpen: boolean;
  onCloseMobile: () => void;
};

export function Sidebar({ collapsed, mobileOpen, onCloseMobile }: SidebarProps) {
  const pathname = usePathname();

  return (
    <>
      {/* Backdrop mobile */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-foreground/40 backdrop-blur-sm lg:hidden"
          aria-hidden="true"
          onClick={onCloseMobile}
        />
      )}

      <aside
        aria-label="Navegacao principal"
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex flex-col border-r border-border bg-background transition-[width,transform] duration-200 ease-out",
          // Desktop: controlado pelo toggle collapsed
          collapsed ? "lg:w-16" : "lg:w-64",
          // Mobile: drawer deslizante. A largura expandida (w-64) eh usada
          // sempre que aberto em mobile, independente do estado collapsed.
          "w-64",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
          "lg:translate-x-0",
        )}
      >
        <div className="flex h-14 items-center justify-between border-b border-border px-4">
          <Link
            href="/dashboard"
            className={cn(
              "flex items-center gap-2 font-semibold tracking-tight",
              collapsed && "lg:justify-center lg:gap-0",
            )}
            aria-label="Ir para o dashboard"
          >
            <span
              aria-hidden="true"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground"
            >
              N
            </span>
            <span
              className={cn(
                "text-sm",
                collapsed && "lg:sr-only",
              )}
            >
              NFS-e SaaS
            </span>
          </Link>
          <button
            type="button"
            onClick={onCloseMobile}
            aria-label="Fechar menu"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <nav
          aria-label="Itens do painel"
          data-help-id="sidebar-navigation"
          className="flex-1 overflow-y-auto p-2"
        >
          <ul className="flex flex-col gap-1">
            {NAV_ITEMS.map((item) => {
              const active =
                pathname === item.href || pathname.startsWith(`${item.href}/`);
              const Icon = item.icon;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onCloseMobile}
                    aria-current={active ? "page" : undefined}
                    title={collapsed ? item.label : undefined}
                    className={cn(
                      "group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      active
                        ? "bg-accent text-accent-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                      collapsed && "lg:justify-center lg:px-0",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                    <span className={cn(collapsed && "lg:sr-only")}>
                      {item.label}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div
          className={cn(
            "border-t border-border p-3 text-xs text-muted-foreground",
            collapsed && "lg:sr-only",
          )}
        >
          v0.0.1 — alpha
        </div>
      </aside>
    </>
  );
}
