"use client";

import { CircleHelp } from "lucide-react";

import { cn } from "@/lib/utils";
import { useHelp } from "./help-provider";

export function HelpButton() {
  const { open, isNew, openHelp, showRouteArticle } = useHelp();

  return (
    <button
      type="button"
      onClick={() => {
        showRouteArticle();
        openHelp();
      }}
      aria-label="Abrir ajuda desta página"
      aria-expanded={open}
      data-help-id="help-button"
      className={cn(
        "relative inline-flex h-9 items-center justify-center gap-1.5 rounded-md border border-border bg-background px-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:px-3",
        open && "bg-accent text-accent-foreground",
      )}
    >
      <CircleHelp className="h-4 w-4" aria-hidden="true" />
      <span className="hidden sm:inline">Ajuda</span>
      {isNew ? (
        <span className="absolute -right-2 -top-2 rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold leading-none text-primary-foreground shadow-sm">
          Novo
        </span>
      ) : null}
    </button>
  );
}
