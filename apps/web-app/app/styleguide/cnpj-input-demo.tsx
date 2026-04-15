"use client";

import { useState } from "react";

import { CNPJInput } from "@/components/ui/cnpj-input";

export function CNPJInputDemo() {
  const [value, setValue] = useState("");
  const [valid, setValid] = useState<boolean | null>(null);

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="space-y-2">
        <label
          htmlFor="cnpj-empty"
          className="text-sm font-medium text-foreground"
        >
          CNPJ (vazio)
        </label>
        <CNPJInput
          id="cnpj-empty"
          value={value}
          onChange={setValue}
          onValidityChange={setValid}
        />
        <p className="text-xs text-muted-foreground">
          Valor normalizado: <code>{value || "—"}</code> · valido:{" "}
          <code>{String(valid)}</code>
        </p>
      </div>

      <div className="space-y-2">
        <label
          htmlFor="cnpj-invalid"
          className="text-sm font-medium text-foreground"
        >
          CNPJ (pre-preenchido invalido)
        </label>
        <CNPJInput id="cnpj-invalid" defaultValue="00000000000190" />
        <p className="text-xs text-muted-foreground">
          DV incorreto — erro visivel imediatamente.
        </p>
      </div>
    </div>
  );
}
