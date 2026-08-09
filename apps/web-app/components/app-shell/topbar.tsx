"use client";

import { Menu, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";
import { Breadcrumbs } from "./breadcrumbs";
import { NotificationsBell } from "./notifications-bell";
import { TenantSwitcher } from "./tenant-switcher";
import { UserMenu } from "./user-menu";
import { HelpButton } from "@/components/help/help-button";

type TopbarProps = {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  onOpenMobile: () => void;
};

export function Topbar({
  collapsed,
  onToggleCollapsed,
  onOpenMobile,
}: TopbarProps) {
  return (
    <header
      className={cn(
        "sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-background/90 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60",
      )}
    >
      <button
        type="button"
        onClick={onOpenMobile}
        aria-label="Abrir menu"
        className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-background text-foreground shadow-sm transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden"
      >
        <Menu className="h-4 w-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        onClick={onToggleCollapsed}
        aria-label={collapsed ? "Expandir sidebar" : "Recolher sidebar"}
        aria-pressed={collapsed}
        className="hidden h-9 w-9 items-center justify-center rounded-md border border-border bg-background text-foreground shadow-sm transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:inline-flex"
      >
        {collapsed ? (
          <PanelLeftOpen className="h-4 w-4" aria-hidden="true" />
        ) : (
          <PanelLeftClose className="h-4 w-4" aria-hidden="true" />
        )}
      </button>

      <div className="min-w-0 flex-1">
        <Breadcrumbs />
      </div>

      <div className="flex items-center gap-2">
        <div className="hidden md:block">
          <TenantSwitcher />
        </div>
        <NotificationsBell />
        <HelpButton />
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
