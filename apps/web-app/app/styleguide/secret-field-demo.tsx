"use client";

import { SecretField } from "@/components/ui/secret-field";

export function SecretFieldDemo() {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="space-y-2">
        <label
          htmlFor="secret-password"
          className="text-sm font-medium text-foreground"
        >
          Senha do PFX
        </label>
        <SecretField
          id="secret-password"
          placeholder="Digite a senha do certificado"
        />
      </div>

      <div className="space-y-2">
        <label
          htmlFor="secret-token"
          className="text-sm font-medium text-foreground"
        >
          Token de API
        </label>
        <SecretField
          id="secret-token"
          defaultValue="nfse_live_5fQz3kT0qHrD8vL2jY"
        />
      </div>
    </div>
  );
}
