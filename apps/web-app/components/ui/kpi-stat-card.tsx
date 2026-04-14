import * as React from "react";
import {
  AlertTriangle,
  Minus,
  TrendingDown,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

export type KPIStatCardState = "ready" | "loading" | "empty" | "error";

export interface KPIStatCardProps
  extends Omit<React.HTMLAttributes<HTMLElement>, "title"> {
  /** Rotulo curto do indicador. */
  title: string;
  /** Valor principal (ja formatado pelo chamador). */
  value?: React.ReactNode;
  /**
   * Variacao percentual vs periodo anterior. Positivo = subida, negativo =
   * queda, 0 = estavel. Quando `undefined`, o delta nao e renderizado.
   */
  deltaPercent?: number;
  /** Serie para a mini-sparkline. Minimo 2 pontos. */
  trendData?: number[];
  /** Icone Lucide opcional, exibido no canto superior direito. */
  icon?: LucideIcon;
  /** Estado visual. Default: "ready". */
  state?: KPIStatCardState;
  /** Dica curta exibida abaixo do valor (ex.: "vs 30 dias anteriores"). */
  hint?: string;
  /** Mensagem exibida quando `state === "error"`. */
  errorMessage?: string;
  /**
   * Rotulo semantico para leitores de tela (padrao: o `title`).
   */
  ariaLabel?: string;
}

const EMPTY_VALUE = "\u2014"; // em dash
const DEFAULT_EMPTY_HINT = "Sem dados";

function formatDelta(deltaPercent: number): string {
  const abs = Math.abs(deltaPercent).toFixed(1).replace(/\.0$/, "");
  if (deltaPercent > 0) return `+${abs}%`;
  if (deltaPercent < 0) return `-${abs}%`;
  return "0%";
}

function deltaTone(deltaPercent: number): {
  className: string;
  Icon: LucideIcon;
  srLabel: string;
} {
  if (deltaPercent > 0) {
    return {
      className: "text-success",
      Icon: TrendingUp,
      srLabel: "aumento",
    };
  }
  if (deltaPercent < 0) {
    return {
      className: "text-destructive",
      Icon: TrendingDown,
      srLabel: "queda",
    };
  }
  return {
    className: "text-muted-foreground",
    Icon: Minus,
    srLabel: "estavel",
  };
}

interface SparklineProps {
  data: number[];
  tone: "up" | "down" | "flat";
}

/**
 * Mini-sparkline em SVG puro (sem dependencia). Renderiza area + linha,
 * normalizando a serie para o viewBox. Decorativa (aria-hidden).
 */
function Sparkline({ data, tone }: SparklineProps) {
  if (data.length < 2) return null;

  const width = 80;
  const height = 24;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const stepX = width / (data.length - 1);

  const points = data.map((v, i) => {
    const x = i * stepX;
    const y = height - ((v - min) / range) * height;
    return [x, y] as const;
  });

  const linePath = points
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`)
    .join(" ");

  const areaPath = `${linePath} L${width.toFixed(2)},${height} L0,${height} Z`;

  const strokeClass =
    tone === "up"
      ? "stroke-success"
      : tone === "down"
        ? "stroke-destructive"
        : "stroke-muted-foreground";
  const fillClass =
    tone === "up"
      ? "fill-success/15"
      : tone === "down"
        ? "fill-destructive/15"
        : "fill-muted-foreground/15";

  return (
    <svg
      aria-hidden="true"
      role="presentation"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className="h-6 w-20 shrink-0"
    >
      <path d={areaPath} className={cn(fillClass)} strokeWidth={0} />
      <path
        d={linePath}
        className={cn(strokeClass)}
        fill="none"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-md bg-muted", className)}
    />
  );
}

/**
 * KPIStatCard (DS-05) — card compacto de indicador para dashboards.
 * Exibe valor grande, delta vs periodo anterior e mini-sparkline
 * opcional (SVG inline). Estados: ready / loading / empty / error.
 */
export const KPIStatCard = React.forwardRef<HTMLElement, KPIStatCardProps>(
  function KPIStatCard(
    {
      title,
      value,
      deltaPercent,
      trendData,
      icon: Icon,
      state = "ready",
      hint,
      errorMessage,
      ariaLabel,
      className,
      ...rest
    },
    ref,
  ) {
    const hasDelta =
      state === "ready" &&
      typeof deltaPercent === "number" &&
      Number.isFinite(deltaPercent);
    const hasSparkline =
      state === "ready" && Array.isArray(trendData) && trendData.length >= 2;

    const sparklineTone: SparklineProps["tone"] = !hasDelta
      ? "flat"
      : (deltaPercent as number) > 0
        ? "up"
        : (deltaPercent as number) < 0
          ? "down"
          : "flat";

    return (
      <article
        ref={ref}
        aria-label={ariaLabel ?? title}
        aria-busy={state === "loading" || undefined}
        data-state={state}
        className={cn(
          "flex flex-col gap-3 rounded-lg border border-border bg-card p-4 text-card-foreground shadow-sm",
          className,
        )}
        {...rest}
      >
        <header className="flex items-start justify-between gap-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {title}
          </p>
          {Icon ? (
            <Icon
              aria-hidden="true"
              className="h-4 w-4 shrink-0 text-muted-foreground"
            />
          ) : null}
        </header>

        {state === "loading" ? (
          <div className="space-y-2">
            <Skeleton className="h-8 w-24" />
            <Skeleton className="h-3 w-32" />
          </div>
        ) : state === "error" ? (
          <div className="flex items-start gap-2 text-sm text-destructive">
            <AlertTriangle
              aria-hidden="true"
              className="h-4 w-4 shrink-0"
            />
            <span>{errorMessage ?? "Nao foi possivel carregar o indicador."}</span>
          </div>
        ) : state === "empty" ? (
          <div className="space-y-1">
            <p className="text-3xl font-semibold tracking-tight text-muted-foreground">
              {EMPTY_VALUE}
            </p>
            <p className="text-xs text-muted-foreground">
              {hint ?? DEFAULT_EMPTY_HINT}
            </p>
          </div>
        ) : (
          <>
            <p className="text-3xl font-semibold tracking-tight">
              {value ?? EMPTY_VALUE}
            </p>
            <div className="flex items-center justify-between gap-3">
              <div className="flex min-w-0 flex-col gap-0.5">
                {hasDelta ? (
                  <DeltaLabel deltaPercent={deltaPercent as number} />
                ) : null}
                {hint ? (
                  <p className="truncate text-xs text-muted-foreground">
                    {hint}
                  </p>
                ) : null}
              </div>
              {hasSparkline ? (
                <Sparkline
                  data={trendData as number[]}
                  tone={sparklineTone}
                />
              ) : null}
            </div>
          </>
        )}
      </article>
    );
  },
);

function DeltaLabel({ deltaPercent }: { deltaPercent: number }) {
  const { className, Icon, srLabel } = deltaTone(deltaPercent);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-xs font-medium",
        className,
      )}
    >
      <Icon aria-hidden="true" className="h-3.5 w-3.5" />
      <span className="sr-only">{srLabel} de </span>
      <span>{formatDelta(deltaPercent)}</span>
    </span>
  );
}
