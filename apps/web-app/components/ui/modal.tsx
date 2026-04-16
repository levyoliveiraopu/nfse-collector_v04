"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  /** Titulo do dialogo (acessivel via aria-labelledby). */
  title: string;
  /** Descricao opcional curta abaixo do titulo. */
  description?: string;
  children: React.ReactNode;
  /** Largura maxima do dialog. Default: max-w-md. */
  maxWidth?: string;
  /** Renderizar botao "X" no canto. Default: true. */
  showCloseButton?: boolean;
  /** Permitir fechar via Esc / clique no backdrop. Default: true. */
  dismissable?: boolean;
}

/**
 * Modal acessivel sem dependencia em Radix. Usa `createPortal` para
 * escapar do contexto do trigger e bloquear o scroll do body enquanto
 * aberto. Fecha em Esc, clique no backdrop e botao "X".
 *
 * Foco basico: o primeiro elemento focavel dentro do conteudo recebe
 * foco no mount; foco fica preso (loop simples por Tab/Shift+Tab) se
 * houver mais de um elemento focavel.
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  maxWidth = "max-w-md",
  showCloseButton = true,
  dismissable = true,
}: ModalProps) {
  const contentRef = React.useRef<HTMLDivElement | null>(null);
  const titleId = React.useId();
  const descId = React.useId();

  // Bloqueia scroll do body enquanto o dialog estiver aberto.
  React.useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  // Fecha com Esc + focus trap simples.
  React.useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape" && dismissable) {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const node = contentRef.current;
      if (!node) return;
      const focusables = node.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) return;
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
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, dismissable, onClose]);

  // Foca o primeiro elemento focavel ao abrir.
  React.useEffect(() => {
    if (!open) return;
    const node = contentRef.current;
    if (!node) return;
    const focusables = node.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (focusables.length > 0) {
      focusables[0].focus();
    } else {
      node.focus();
    }
  }, [open]);

  if (!open) return null;
  if (typeof window === "undefined") return null;

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={description ? descId : undefined}
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-foreground/40 p-4 backdrop-blur-sm sm:items-center"
      onMouseDown={(event) => {
        if (!dismissable) return;
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        ref={contentRef}
        tabIndex={-1}
        className={cn(
          "relative w-full rounded-lg border border-border bg-background text-foreground shadow-lg outline-none",
          maxWidth,
        )}
      >
        <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <h2 id={titleId} className="text-base font-semibold tracking-tight">
              {title}
            </h2>
            {description ? (
              <p
                id={descId}
                className="mt-1 text-sm text-muted-foreground"
              >
                {description}
              </p>
            ) : null}
          </div>
          {showCloseButton ? (
            <button
              type="button"
              onClick={onClose}
              aria-label="Fechar"
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          ) : null}
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
