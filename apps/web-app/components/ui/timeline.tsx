import * as React from "react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export type TimelineTone =
  | "default"
  | "success"
  | "warning"
  | "destructive"
  | "info";

export interface TimelineItem {
  id: string;
  /** ISO 8601 ou `Date`. Renderizado via `toLocaleString('pt-BR')`. */
  timestamp: string | Date;
  title: React.ReactNode;
  description?: React.ReactNode;
  tone?: TimelineTone;
  icon?: LucideIcon;
}

export interface TimelineProps
  extends Omit<React.HTMLAttributes<HTMLOListElement>, "children"> {
  items: TimelineItem[];
  /** Rotulo semantico para leitores de tela. Default: "Linha do tempo". */
  ariaLabel?: string;
}

const TONE_DOT: Record<TimelineTone, string> = {
  default: "bg-muted-foreground",
  success: "bg-success",
  warning: "bg-warning",
  destructive: "bg-destructive",
  info: "bg-primary",
};

function formatTimestamp(value: string | Date): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("pt-BR");
}

/**
 * Timeline (DS-08) — lista vertical de eventos com bullet colorido e
 * linha conectando itens. Usada para visualizar execucoes e
 * ocorrencias.
 */
export const Timeline = React.forwardRef<HTMLOListElement, TimelineProps>(
  function Timeline(
    { items, ariaLabel = "Linha do tempo", className, ...rest },
    ref,
  ) {
    return (
      <ol
        ref={ref}
        aria-label={ariaLabel}
        className={cn("relative flex flex-col gap-4", className)}
        {...rest}
      >
        {items.map((item, index) => {
          const tone: TimelineTone = item.tone ?? "default";
          const Icon = item.icon;
          const isLast = index === items.length - 1;
          return (
            <li
              key={item.id}
              data-tone={tone}
              className="relative flex gap-3 pl-6"
            >
              {!isLast ? (
                <span
                  aria-hidden="true"
                  className="absolute left-[7px] top-5 h-[calc(100%_-_0.25rem)] w-px bg-border"
                />
              ) : null}
              <span
                aria-hidden="true"
                className={cn(
                  "absolute left-0 top-1.5 flex h-4 w-4 items-center justify-center rounded-full ring-2 ring-background",
                  TONE_DOT[tone],
                )}
              >
                {Icon ? (
                  <Icon className="h-2.5 w-2.5 text-background" aria-hidden="true" />
                ) : null}
              </span>
              <div className="flex min-w-0 flex-col gap-1">
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <p className="text-sm font-medium text-foreground">
                    {item.title}
                  </p>
                  <time
                    dateTime={
                      item.timestamp instanceof Date
                        ? item.timestamp.toISOString()
                        : item.timestamp
                    }
                    className="text-xs text-muted-foreground"
                  >
                    {formatTimestamp(item.timestamp)}
                  </time>
                </div>
                {item.description ? (
                  <p className="text-sm text-muted-foreground">
                    {item.description}
                  </p>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    );
  },
);
