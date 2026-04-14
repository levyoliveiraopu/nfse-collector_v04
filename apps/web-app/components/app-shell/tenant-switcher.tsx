"use client";

import { Building2, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { useDropdown } from "./use-dropdown";

export function TenantSwitcher() {
  const { open, setOpen, containerRef } = useDropdown();

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "inline-flex h-9 items-center gap-2 rounded-md border border-border bg-background px-3 text-sm font-medium text-foreground shadow-sm transition hover:bg-accent hover:text-accent-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        <Building2 className="h-4 w-4" aria-hidden="true" />
        <span className="max-w-[10rem] truncate">Selecionar tenant</span>
        <ChevronsUpDown
          className="h-3.5 w-3.5 text-muted-foreground"
          aria-hidden="true"
        />
      </button>
      {open && (
        <div
          role="listbox"
          aria-label="Tenants disponiveis"
          className="absolute right-0 z-50 mt-2 w-64 rounded-md border border-border bg-popover p-3 text-popover-foreground shadow-md"
        >
          <p className="text-xs text-muted-foreground">
            Em breve voce podera alternar entre tenants aqui.
          </p>
        </div>
      )}
    </div>
  );
}
