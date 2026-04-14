"use client";

import { Bell } from "lucide-react";
import { cn } from "@/lib/utils";
import { useDropdown } from "./use-dropdown";

export function NotificationsBell() {
  const { open, setOpen, containerRef } = useDropdown();

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label="Notificacoes"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "relative inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-background text-foreground shadow-sm transition hover:bg-accent hover:text-accent-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        <Bell className="h-4 w-4" aria-hidden="true" />
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Notificacoes recentes"
          className="absolute right-0 z-50 mt-2 w-72 rounded-md border border-border bg-popover p-4 text-popover-foreground shadow-md"
        >
          <p className="text-sm font-medium">Notificacoes</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Voce nao tem notificacoes no momento.
          </p>
        </div>
      )}
    </div>
  );
}
