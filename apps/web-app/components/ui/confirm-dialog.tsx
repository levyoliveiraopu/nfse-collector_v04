"use client";

import * as React from "react";

import {
  Dialog,
  DialogBody,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

export type ConfirmDialogTone = "default" | "destructive";

export interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  description?: React.ReactNode;
  /** Rotulo do botao de confirmacao. Default: "Confirmar". */
  confirmLabel?: string;
  /** Rotulo do botao de cancelar. Default: "Cancelar". */
  cancelLabel?: string;
  /**
   * Texto que o usuario deve digitar para habilitar a confirmacao.
   * Quando fornecido, o botao "Confirmar" fica desabilitado ate que o
   * input case exatamente (apos `trim`). Comparacao case-sensitive.
   */
  confirmPhrase?: string;
  tone?: ConfirmDialogTone;
  /** Bloqueia o dialog enquanto a confirmacao esta em andamento. */
  busy?: boolean;
}

/**
 * ConfirmDialog (DS-08) — confirmacao generica, com modo destrutivo
 * que exige "digite X para confirmar".
 */
export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  confirmPhrase,
  tone = "default",
  busy = false,
}: ConfirmDialogProps) {
  const titleId = React.useId();
  const descId = React.useId();
  const phraseInputId = React.useId();
  const [typed, setTyped] = React.useState("");

  React.useEffect(() => {
    if (!open) setTyped("");
  }, [open]);

  const requiresPhrase =
    typeof confirmPhrase === "string" && confirmPhrase.length > 0;
  const phraseMatches = requiresPhrase
    ? typed.trim() === confirmPhrase
    : true;
  const disabled = busy || !phraseMatches;

  const confirmClass =
    tone === "destructive"
      ? "bg-destructive text-destructive-foreground"
      : "bg-primary text-primary-foreground";

  return (
    <Dialog
      open={open}
      onClose={() => {
        if (busy) return;
        onClose();
      }}
      labelledBy={titleId}
      describedBy={description ? descId : undefined}
      closeOnOverlayClick={!busy}
      showCloseButton={!busy}
    >
      <DialogHeader>
        <DialogTitle id={titleId}>{title}</DialogTitle>
        {description ? (
          <DialogDescription id={descId}>{description}</DialogDescription>
        ) : null}
      </DialogHeader>

      {requiresPhrase ? (
        <DialogBody>
          <label
            htmlFor={phraseInputId}
            className="text-sm text-foreground"
          >
            Para confirmar, digite{" "}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
              {confirmPhrase}
            </code>
          </label>
          <input
            id={phraseInputId}
            type="text"
            autoComplete="off"
            spellCheck={false}
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            disabled={busy}
            aria-invalid={!phraseMatches}
            className="inline-flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none transition focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
          />
        </DialogBody>
      ) : null}

      <DialogFooter>
        <button
          type="button"
          onClick={onClose}
          disabled={busy}
          className="inline-flex h-9 items-center rounded-md border border-border bg-background px-4 text-sm font-medium text-foreground shadow-sm transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
        >
          {cancelLabel}
        </button>
        <button
          type="button"
          onClick={() => {
            if (disabled) return;
            void onConfirm();
          }}
          disabled={disabled}
          data-tone={tone}
          className={cn(
            "inline-flex h-9 items-center rounded-md px-4 text-sm font-medium shadow-sm transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
            confirmClass,
          )}
        >
          {confirmLabel}
        </button>
      </DialogFooter>
    </Dialog>
  );
}
