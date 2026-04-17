import * as React from "react";

import { cn } from "@/lib/utils";

export interface LoadingSkeletonProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "children"> {
  /** Renderiza N barras horizontais empilhadas. */
  lines?: number;
  /** Renderiza uma grade de linhas (rows x columns) estilo tabela. */
  rows?: number;
  /** Numero de colunas quando `rows` estiver definido. Default: 4. */
  columns?: number;
  /** Rotulo semantico para leitores de tela. Default: "Carregando". */
  ariaLabel?: string;
}

function Bar({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn("h-3 animate-pulse rounded-md bg-muted", className)}
    />
  );
}

/**
 * LoadingSkeleton (DS-08) — placeholders enquanto dados carregam. Suporta
 * duas variantes: `lines` (barras empilhadas) e `rows` (grade tabular).
 * Quando ambas estao definidas, `rows` prevalece.
 */
export const LoadingSkeleton = React.forwardRef<
  HTMLDivElement,
  LoadingSkeletonProps
>(function LoadingSkeleton(
  {
    lines = 3,
    rows,
    columns = 4,
    ariaLabel = "Carregando",
    className,
    ...rest
  },
  ref,
) {
  const mode: "rows" | "lines" =
    typeof rows === "number" && rows > 0 ? "rows" : "lines";

  return (
    <div
      ref={ref}
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label={ariaLabel}
      data-variant={mode}
      className={cn("w-full", className)}
      {...rest}
    >
      <span className="sr-only">{ariaLabel}</span>
      {mode === "lines" ? (
        <div className="space-y-2">
          {Array.from({ length: Math.max(1, lines) }).map((_, i) => (
            <Bar
              key={i}
              className={i === Math.max(1, lines) - 1 ? "w-2/3" : "w-full"}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {Array.from({ length: rows as number }).map((_, rowIndex) => (
            <div
              key={rowIndex}
              className="grid gap-3"
              style={{
                gridTemplateColumns: `repeat(${Math.max(1, columns)}, minmax(0, 1fr))`,
              }}
            >
              {Array.from({ length: Math.max(1, columns) }).map((__, colIndex) => (
                <Bar key={colIndex} className="h-4" />
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
});
