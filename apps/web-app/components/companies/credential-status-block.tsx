"use client";

/**
 * CredentialStatusBlock (APP-04) — bloco informativo com badge de status,
 * fingerprint SHA-256 em font-mono e janela de validade do certificado.
 * Renderiza estado "Nao configurada" quando `credential === null`.
 */
import * as React from "react";

import { StatusBadge } from "@/components/ui/status-badge";
import {
  type Credential,
  decideCredentialBadge,
  formatFingerprint,
} from "@/lib/companies/credentials";

const DATE_FORMATTER = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return DATE_FORMATTER.format(d);
}

export interface CredentialStatusBlockProps {
  credential: Credential | null;
  /** Override de `new Date()` para testes deterministicos. */
  now?: Date;
  /** Sinaliza que o usuario acabou de subir um PFX cujo CN nao casa. */
  cnMismatchWarning?: boolean;
}

export function CredentialStatusBlock({
  credential,
  now,
  cnMismatchWarning,
}: CredentialStatusBlockProps) {
  const decision = decideCredentialBadge(credential, now);
  const fingerprint = formatFingerprint(credential?.cert_fingerprint ?? null);

  return (
    <div
      className="flex flex-col gap-4 rounded-lg border border-border bg-card p-4 text-card-foreground shadow-sm"
      data-testid="credential-status-block"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-xs uppercase tracking-wide text-muted-foreground">
            Status da credencial
          </span>
          <StatusBadge variant={decision.variant} label={decision.label} />
        </div>
        {credential?.cert_not_after ? (
          <div className="flex flex-col items-end gap-0.5 text-right">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Valido ate
            </span>
            <span className="text-sm font-medium text-foreground">
              {formatDate(credential.cert_not_after)}
            </span>
          </div>
        ) : null}
      </div>

      {credential ? (
        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-0.5">
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">
              Emitido em
            </dt>
            <dd className="text-sm text-foreground">
              {formatDate(credential.cert_not_before)}
            </dd>
          </div>
          <div className="flex flex-col gap-0.5 sm:col-span-2">
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">
              Fingerprint SHA-256
            </dt>
            <dd
              className="break-all font-mono text-xs text-foreground"
              data-testid="credential-fingerprint"
            >
              {fingerprint || "—"}
            </dd>
          </div>
        </dl>
      ) : (
        <p className="text-sm text-muted-foreground">
          Nenhum certificado A1 foi enviado para esta empresa. Envie um
          arquivo <code className="font-mono">.pfx</code> valido para
          habilitar a coleta.
        </p>
      )}

      {cnMismatchWarning && credential?.cn_matches_cnpj === false ? (
        <p
          role="alert"
          className="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning-foreground dark:text-warning"
        >
          O <strong>CN</strong> do certificado nao contem o CNPJ desta
          empresa. A credencial foi aceita, mas confirme se o PFX
          pertence ao estabelecimento correto antes de iniciar coletas.
        </p>
      ) : null}
    </div>
  );
}
