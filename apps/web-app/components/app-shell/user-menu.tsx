"use client";

import { LogOut, User as UserIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useDropdown } from "./use-dropdown";

export function UserMenu() {
  const { open, setOpen, containerRef } = useDropdown();

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "inline-flex h-9 items-center gap-2 rounded-md border border-border bg-background pl-1 pr-3 text-sm font-medium text-foreground shadow-sm transition hover:bg-accent hover:text-accent-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        <span
          aria-hidden="true"
          className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-primary-foreground"
        >
          <UserIcon className="h-3.5 w-3.5" />
        </span>
        <span className="hidden sm:inline">Minha conta</span>
      </button>
      {open && (
        <div
          role="menu"
          aria-label="Menu do usuario"
          className="absolute right-0 z-50 mt-2 w-56 overflow-hidden rounded-md border border-border bg-popover text-popover-foreground shadow-md"
        >
          <div className="border-b border-border px-3 py-2 text-xs text-muted-foreground">
            Sessao de exemplo
          </div>
          <button
            role="menuitem"
            type="button"
            disabled
            className="flex w-full items-center gap-2 px-3 py-2 text-sm text-muted-foreground disabled:cursor-not-allowed"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            Sair (em breve)
          </button>
        </div>
      )}
    </div>
  );
}
