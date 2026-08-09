"use client";

import { usePathname } from "next/navigation";
import { CircleHelp } from "lucide-react";

import { resolveHelpEntry } from "@/lib/help/catalog";
import { HelpArticle } from "./help-article";

export function AuthPageHelp() {
  const pathname = usePathname();
  const entry = resolveHelpEntry(pathname, "viewer");

  if (entry.routeKey !== "access") return null;

  return (
    <details className="mt-5 rounded-md border border-border bg-muted/30">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <CircleHelp className="h-4 w-4 text-primary" aria-hidden="true" />
        Ajuda para esta etapa
      </summary>
      <div className="border-t border-border px-3 py-3">
        <HelpArticle entry={entry} />
      </div>
    </details>
  );
}
