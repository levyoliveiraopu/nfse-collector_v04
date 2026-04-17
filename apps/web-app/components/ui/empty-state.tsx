import * as React from "react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export interface EmptyStateAction {
  label: string;
  onClick?: () => void;
  href?: string;
}

export interface EmptyStateProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  title: string;
  description?: React.ReactNode;
  icon?: LucideIcon;
  action?: EmptyStateAction;
  /** Rotulo semantico para leitores de tela. Default: o `title`. */
  ariaLabel?: string;
}

/**
 * EmptyState (DS-08) — card neutro para listas/telas sem dados.
 * Combina icone Lucide opcional, titulo, descricao e CTA opcional.
 */
export const EmptyState = React.forwardRef<HTMLDivElement, EmptyStateProps>(
  function EmptyState(
    { title, description, icon: Icon, action, ariaLabel, className, ...rest },
    ref,
  ) {
    return (
      <div
        ref={ref}
        role="status"
        aria-live="polite"
        aria-label={ariaLabel ?? title}
        className={cn(
          "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-card p-8 text-center text-card-foreground",
          className,
        )}
        {...rest}
      >
        {Icon ? (
          <Icon
            aria-hidden="true"
            className="h-10 w-10 text-muted-foreground"
          />
        ) : null}
        <div className="space-y-1">
          <p className="text-base font-semibold tracking-tight">{title}</p>
          {description ? (
            <p className="text-sm text-muted-foreground">{description}</p>
          ) : null}
        </div>
        {action ? (
          action.href ? (
            <a
              href={action.href}
              className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {action.label}
            </a>
          ) : (
            <button
              type="button"
              onClick={action.onClick}
              className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {action.label}
            </button>
          )
        ) : null}
      </div>
    );
  },
);
