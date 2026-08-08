"use client";

import * as React from "react";
import { Calendar } from "lucide-react";

import { cn } from "@/lib/utils";
import {
  type PeriodPreset,
  type PeriodRange,
  PRESET_LABELS,
  computePresetRange,
  isOrderedRange,
  isValidISODate,
} from "@/lib/date/period";

export type { PeriodPreset, PeriodRange };

export interface PeriodPickerProps {
  value?: PeriodRange;
  defaultValue?: PeriodRange;
  /** Disparado quando o usuario escolhe preset valido ou range custom valido. */
  onChange?: (range: PeriodRange) => void;
  /** Oculta botoes de preset. Default: mostra os 4. */
  hidePresets?: boolean;
  className?: string;
  /** Data de referencia para os presets (default: hoje). Util para testes. */
  today?: Date;
  /** Id de uma orientacao visivel associada aos dois campos de data. */
  descriptionId?: string;
}

const PRESETS: Exclude<PeriodPreset, "custom">[] = [
  "current_month",
  "previous_month",
  "last_7d",
  "last_30d",
];

function defaultRange(today: Date | undefined): PeriodRange {
  return computePresetRange("last_30d", today);
}

/**
 * PeriodPicker (DS-07) — seleciona um intervalo de datas com presets
 * rapidos (mes atual, mes anterior, 7d, 30d) e dois `input[type=date]`
 * para range custom. Emite `onChange` somente com ranges validos.
 */
export const PeriodPicker = React.forwardRef<HTMLDivElement, PeriodPickerProps>(
  function PeriodPicker(
    {
      value,
      defaultValue,
      onChange,
      hidePresets = false,
      className,
      today,
      descriptionId,
    },
    ref,
  ) {
    const isControlled = value !== undefined;
    const [internal, setInternal] = React.useState<PeriodRange>(
      () => defaultValue ?? defaultRange(today),
    );
    const [customError, setCustomError] = React.useState<string | null>(null);

    const current = isControlled ? (value as PeriodRange) : internal;

    const commit = (next: PeriodRange) => {
      if (!isControlled) setInternal(next);
      onChange?.(next);
    };

    const handlePreset = (preset: Exclude<PeriodPreset, "custom">) => {
      const range = computePresetRange(preset, today);
      setCustomError(null);
      commit(range);
    };

    const handleCustom = (field: "from" | "to", raw: string) => {
      const nextFrom = field === "from" ? raw : current.from;
      const nextTo = field === "to" ? raw : current.to;
      const candidate: PeriodRange = {
        from: nextFrom,
        to: nextTo,
        preset: "custom",
      };
      if (!isValidISODate(nextFrom) || !isValidISODate(nextTo)) {
        // Atualiza UI localmente enquanto edita, mas nao emite change.
        if (!isControlled) setInternal(candidate);
        setCustomError(null);
        return;
      }
      if (!isOrderedRange(nextFrom, nextTo)) {
        setCustomError("Data inicial deve ser anterior ou igual a final.");
        if (!isControlled) setInternal(candidate);
        return;
      }
      setCustomError(null);
      commit(candidate);
    };

    return (
      <div ref={ref} className={cn("flex flex-col gap-3", className)}>
        {hidePresets ? null : (
          <div
            role="group"
            aria-label="Presets de periodo"
            className="flex flex-wrap gap-2"
          >
            {PRESETS.map((preset) => {
              const active = current.preset === preset;
              return (
                <button
                  key={preset}
                  type="button"
                  onClick={() => handlePreset(preset)}
                  aria-pressed={active}
                  className={cn(
                    "inline-flex h-8 items-center rounded-md border px-3 text-xs font-medium transition",
                    "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    active
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-input bg-background text-foreground hover:bg-accent hover:text-accent-foreground",
                  )}
                >
                  {PRESET_LABELS[preset]}
                </button>
              );
            })}
          </div>
        )}

        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Calendar aria-hidden="true" className="h-3.5 w-3.5" />
              De
            </span>
            <input
              type="date"
              value={current.from}
              onChange={(e) => handleCustom("from", e.target.value)}
              aria-label="Data inicial"
              aria-describedby={descriptionId}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Calendar aria-hidden="true" className="h-3.5 w-3.5" />
              Ate
            </span>
            <input
              type="date"
              value={current.to}
              onChange={(e) => handleCustom("to", e.target.value)}
              aria-label="Data final"
              aria-describedby={descriptionId}
              min={current.from}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </label>
        </div>

        {customError ? (
          <p role="alert" className="text-xs text-destructive">
            {customError}
          </p>
        ) : null}
      </div>
    );
  },
);
