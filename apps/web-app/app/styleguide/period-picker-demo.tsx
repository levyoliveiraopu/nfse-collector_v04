"use client";

import { useState } from "react";

import {
  PeriodPicker,
  type PeriodRange,
} from "@/components/ui/period-picker";

export function PeriodPickerDemo() {
  const [range, setRange] = useState<PeriodRange | null>(null);

  return (
    <div className="space-y-3">
      <PeriodPicker onChange={setRange} />
      <p className="text-xs text-muted-foreground">
        Selecionado:{" "}
        <code>
          {range
            ? `${range.from} → ${range.to} (${range.preset})`
            : "—"}
        </code>
      </p>
    </div>
  );
}
