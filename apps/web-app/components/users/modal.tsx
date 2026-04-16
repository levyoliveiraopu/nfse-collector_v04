"use client";

import * as React from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

type ModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  /** Label opcional para o botao de fechar (default: "Fechar"). */
  closeLabel?: string;
  children: React.ReactNode;
  className?: string;
};

/**
 * Modal leve sem Radix — segue o padrao do AppShell (dropdowns fecham em
 * click-outside + Esc). Acessivel: role=dialog, aria-labelledby e foco
 * devolvido para o invocador no close.
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  closeLabel = "Fechar",
  children,
  className,
}: ModalProps) {
  const titleId = React.useId();
  const descId = React.useId();
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const invokerRef = React.useRef<Element | null>(null);

  React.useEffect(() => {
    if (!open) return;
    invokerRef.current = document.activeElement;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    }
    document.addEventListener("keydown", onKey);
    // Foca o primeiro elemento focavel no proximo tick.
    const node = containerRef.current;
    const focusable = node?.querySelector<HTMLElement>(
      "input, select, textarea, button",
    );
    focusable?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      if (invokerRef.current instanceof HTMLElement) {
        invokerRef.current.focus();
      }
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 backdrop-blur-sm p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        className={cn(
          "w-full max-w-md rounded-lg border border-border bg-background p-5 text-foreground shadow-lg",
          className,
        )}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 id={titleId} className="text-lg font-semibold">
              {title}
            </h2>
            {description ? (
              <p id={descId} className="mt-1 text-sm text-muted-foreground">
                {description}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={closeLabel}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  destructive,
  loading,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Modal open={open} onClose={onCancel} title={title} description={description}>
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {cancelLabel}
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={loading}
          className={cn(
            "inline-flex h-9 items-center rounded-md px-3 text-sm font-medium text-primary-foreground shadow-sm transition disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            destructive
              ? "bg-destructive hover:bg-destructive/90"
              : "bg-primary hover:bg-primary/90",
          )}
        >
          {loading ? "Processando..." : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
