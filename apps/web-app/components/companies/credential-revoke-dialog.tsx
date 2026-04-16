"use client";

/**
 * CredentialRevokeDialog (APP-04) — confirmacao destrutiva. O submit so
 * libera se o usuario digitar literalmente a palavra `REVOGAR`.
 */
import * as React from "react";
import { Loader2 } from "lucide-react";

import {
  Dialog,
  DialogBody,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { CredentialApiError } from "@/lib/companies/credentials";

export interface CredentialRevokeDialogProps {
  open: boolean;
  onClose: () => void;
  onRevoke: () => Promise<{ revoked: string[] }>;
  onRevoked?: (revoked: string[]) => void;
}

const CONFIRMATION_WORD = "REVOGAR";

export function CredentialRevokeDialog({
  open,
  onClose,
  onRevoke,
  onRevoked,
}: CredentialRevokeDialogProps) {
  const [confirmation, setConfirmation] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open) {
      setConfirmation("");
      setError(null);
      setSubmitting(false);
    }
  }, [open]);

  const canSubmit =
    confirmation.trim().toUpperCase() === CONFIRMATION_WORD && !submitting;

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await onRevoke();
      onRevoked?.(result.revoked);
      onClose();
    } catch (err) {
      if (err instanceof CredentialApiError) {
        if (err.code === "not_configured" || err.code === "not_found") {
          setError("Nenhuma credencial ativa para revogar.");
        } else if (err.code === "forbidden") {
          setError("Voce nao tem permissao para revogar.");
        } else {
          setError(err.message || "Nao foi possivel revogar a credencial.");
        }
      } else {
        setError(
          err instanceof Error
            ? err.message
            : "Nao foi possivel revogar a credencial.",
        );
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={submitting ? () => {} : onClose}
      labelledBy="credential-revoke-title"
      describedBy="credential-revoke-desc"
    >
      <DialogHeader>
        <DialogTitle id="credential-revoke-title">
          Revogar credencial A1
        </DialogTitle>
        <DialogDescription id="credential-revoke-desc">
          Esta acao marca a credencial atual como revogada e remove o
          PFX do storage. Coletas em andamento podem falhar ate que uma
          nova credencial seja enviada.
        </DialogDescription>
      </DialogHeader>
      <form onSubmit={handleSubmit}>
        <DialogBody>
          <label
            htmlFor="credential-revoke-confirmation"
            className="flex flex-col gap-1 text-xs font-medium text-foreground"
          >
            Digite <span className="font-mono">{CONFIRMATION_WORD}</span>
            {" "}para confirmar
            <input
              id="credential-revoke-confirmation"
              value={confirmation}
              onChange={(e) => setConfirmation(e.target.value)}
              disabled={submitting}
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              autoFocus
              className="mt-1 h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
            />
          </label>
          {error ? (
            <p
              role="alert"
              className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive"
              data-testid="credential-revoke-error"
            >
              {error}
            </p>
          ) : null}
        </DialogBody>
        <DialogFooter>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-4 text-sm font-medium transition hover:bg-accent hover:text-accent-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={!canSubmit}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-destructive px-4 text-sm font-medium text-destructive-foreground transition hover:bg-destructive/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? (
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
            ) : null}
            Revogar credencial
          </button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
