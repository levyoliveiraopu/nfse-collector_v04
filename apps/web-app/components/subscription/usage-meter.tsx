import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import type { SubscriptionMetric } from "@/lib/subscription/mock";

export type UsageTone = "ok" | "warn" | "full";

export type UsageMeterProps = {
  title: string;
  metric: SubscriptionMetric;
  icon: LucideIcon;
};

function usageTone(used: number, limit: number): UsageTone {
  if (limit <= 0) return "ok";
  const ratio = used / limit;
  if (ratio >= 1) return "full";
  if (ratio >= 0.8) return "warn";
  return "ok";
}

function formatPercent(used: number, limit: number): string {
  if (limit <= 0) return "-";
  const pct = Math.min(100, Math.round((used / limit) * 100));
  return `${pct}%`;
}

const BAR_COLOR: Record<UsageTone, string> = {
  ok: "bg-primary",
  warn: "bg-warning",
  full: "bg-destructive",
};

export function UsageMeter({ title, metric, icon: Icon }: UsageMeterProps) {
  const { used, limit } = metric;
  const tone = usageTone(used, limit);
  const pctLabel = formatPercent(used, limit);
  const pctWidth = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;

  return (
    <article
      aria-label={title}
      data-tone={tone}
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4 text-card-foreground shadow-sm"
    >
      <header className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {title}
        </p>
        <Icon
          aria-hidden="true"
          className="h-4 w-4 shrink-0 text-muted-foreground"
        />
      </header>
      <div className="flex items-baseline gap-2">
        <p className="text-3xl font-semibold tracking-tight">{used}</p>
        <p className="text-sm text-muted-foreground">
          / {limit} <span className="text-xs">({pctLabel})</span>
        </p>
      </div>
      <div
        role="progressbar"
        aria-valuenow={used}
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-label={`${title}: ${used} de ${limit}`}
        className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
      >
        <div
          className={cn("h-full transition-all", BAR_COLOR[tone])}
          style={{ width: `${pctWidth}%` }}
        />
      </div>
    </article>
  );
}
