"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { NAV_ITEMS } from "./nav-items";

const LABEL_OVERRIDES: Record<string, string> = Object.fromEntries(
  NAV_ITEMS.map((item) => [item.href, item.label]),
);

function humanize(segment: string): string {
  const decoded = decodeURIComponent(segment).replace(/-/g, " ");
  return decoded.charAt(0).toUpperCase() + decoded.slice(1);
}

export function Breadcrumbs() {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  // Constroi pares [href, label] acumulando segmentos.
  const crumbs = segments.map((segment, i) => {
    const href = "/" + segments.slice(0, i + 1).join("/");
    const label = LABEL_OVERRIDES[href] ?? humanize(segment);
    return { href, label };
  });

  if (crumbs.length === 0) return null;

  return (
    <nav aria-label="Trilha" className="min-w-0">
      <ol className="flex items-center gap-1 text-sm text-muted-foreground">
        {crumbs.map((crumb, i) => {
          const isLast = i === crumbs.length - 1;
          return (
            <li key={crumb.href} className="flex min-w-0 items-center gap-1">
              {i > 0 && (
                <ChevronRight
                  className="h-3.5 w-3.5 shrink-0 text-muted-foreground/60"
                  aria-hidden="true"
                />
              )}
              {isLast ? (
                <span
                  aria-current="page"
                  className="truncate font-medium text-foreground"
                >
                  {crumb.label}
                </span>
              ) : (
                <Link
                  href={crumb.href}
                  className="truncate rounded-sm hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {crumb.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
