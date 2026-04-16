"use client";

/**
 * Dialog — modal acessivel minimalista (APP-04).
 *
 * Sem Radix (alinhado com DS-03). Features:
 * - `role="dialog"` + `aria-modal="true"` + `aria-labelledby`.
 * - Fecha com Escape e click no overlay (se `closeOnOverlayClick !== false`).
 * - Impede scroll do body enquanto aberto.
 * - Foca o primeiro elemento focavel ao abrir; devolve foco ao trigger ao
 *   fechar.
 * - Focus trap simples (Tab/Shift+Tab rotacionam pelos focaveis).
 *
 * Uso:
 * ```tsx
 * <Dialog open={open} onClose={() => setOpen(false)} labelledBy="t">
 *   <DialogHeader>
 *     <DialogTitle id="t">Titulo</DialogTitle>
 *   </DialogHeader>
 *   <DialogBody>...</DialogBody>
 *   <DialogFooter>...</DialogFooter>
 * </Dialog>
 * ```
 */
import * as React from "react";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  /** `id` do elemento que rotula o dialog (DialogTitle). */
  labelledBy?: string;
  /** `id` do elemento que descreve o dialog. */
  describedBy?: string;
  closeOnOverlayClick?: boolean;
  /** Mostra botao `X` no canto superior direito. Default: true. */
  showCloseButton?: boolean;
  className?: string;
  children: React.ReactNode;
}

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Dialog({
  open,
  onClose,
  labelledBy,
  describedBy,
  closeOnOverlayClick = true,
  showCloseButton = true,
  className,
  children,
}: DialogProps) {
  const contentRef = React.useRef<HTMLDivElement>(null);
  const triggerRef = React.useRef<HTMLElement | null>(null);

  // Trava o scroll do body enquanto aberto.
  React.useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  // Gerencia foco inicial e retorno.
  React.useEffect(() => {
    if (!open) return;
    triggerRef.current = (document.activeElement as HTMLElement) ?? null;
    const node = contentRef.current;
    if (node) {
      const focusables = Array.from(
        node.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      );
      (focusables[0] ?? node).focus();
    }
    return () => {
      triggerRef.current?.focus?.();
    };
  }, [open]);

  // Escape + focus trap.
  React.useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key === "Tab" && contentRef.current) {
        const focusables = Array.from(
          contentRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
        ).filter((el) => !el.hasAttribute("data-focus-skip"));
        if (focusables.length === 0) {
          event.preventDefault();
          return;
        }
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        const active = document.activeElement as HTMLElement | null;
        if (event.shiftKey && active === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && active === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handleKeyDown, true);
    return () => document.removeEventListener("keydown", handleKeyDown, true);
  }, [open, onClose]);

  if (!open) return null;

  const handleOverlayClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!closeOnOverlayClick) return;
    if (event.target === event.currentTarget) onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 p-4 backdrop-blur-sm"
      onClick={handleOverlayClick}
      data-testid="dialog-overlay"
    >
      <div
        ref={contentRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        tabIndex={-1}
        className={cn(
          "relative flex w-full max-w-md flex-col gap-4 rounded-lg border border-border bg-card p-6 text-card-foreground shadow-lg outline-none",
          className,
        )}
      >
        {showCloseButton ? (
          <button
            type="button"
            aria-label="Fechar"
            onClick={onClose}
            className="absolute right-3 top-3 inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition hover:bg-accent hover:text-accent-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X aria-hidden="true" className="h-4 w-4" />
          </button>
        ) : null}
        {children}
      </div>
    </div>
  );
}

export function DialogHeader({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("flex flex-col gap-1", className)}>{children}</div>;
}

export function DialogTitle({
  id,
  children,
  className,
}: {
  id?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <h2 id={id} className={cn("text-lg font-semibold tracking-tight", className)}>
      {children}
    </h2>
  );
}

export function DialogDescription({
  id,
  children,
  className,
}: {
  id?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p id={id} className={cn("text-sm text-muted-foreground", className)}>
      {children}
    </p>
  );
}

export function DialogBody({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("flex flex-col gap-3", className)}>{children}</div>;
}

export function DialogFooter({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-2",
        className,
      )}
    >
      {children}
    </div>
  );
}
