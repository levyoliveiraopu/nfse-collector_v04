"use client";

import * as React from "react";
import { AlertTriangle } from "lucide-react";

import { cn } from "@/lib/utils";

export interface ErrorBoundaryFallbackProps {
  error: Error;
  reset: () => void;
}

export interface ErrorBoundaryProps {
  children: React.ReactNode;
  /** Callback invocado no clique de "Tentar novamente". Chamado apos o reset. */
  onRetry?: () => void;
  /** Callback para telemetria. Recebe o erro e o `componentStack`. */
  onError?: (error: Error, info: React.ErrorInfo) => void;
  /** Fallback custom (funcao ou node). Sobrescreve a UI default. */
  fallback?:
    | React.ReactNode
    | ((props: ErrorBoundaryFallbackProps) => React.ReactNode);
  className?: string;
}

interface State {
  error: Error | null;
}

/**
 * ErrorBoundary (DS-08) — captura erros de render em toda a subarvore e
 * mostra UI de fallback com botao "Tentar novamente".
 *
 * React so permite capturar erros de render via class component;
 * erros assincronos (effects, event handlers, setTimeout) nao caem
 * aqui — use try/catch ou handlers globais para isso.
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    this.props.onError?.(error, info);
  }

  reset = () => {
    this.setState({ error: null });
    this.props.onRetry?.();
  };

  render() {
    const { error } = this.state;
    const { children, fallback, className } = this.props;

    if (error === null) return children;

    if (typeof fallback === "function") {
      return fallback({ error, reset: this.reset });
    }
    if (fallback !== undefined) {
      return fallback;
    }

    return (
      <div
        role="alert"
        aria-live="assertive"
        className={cn(
          "flex flex-col items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/5 p-6 text-destructive",
          className,
        )}
      >
        <div className="flex items-start gap-2">
          <AlertTriangle aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0" />
          <div className="space-y-1">
            <p className="text-sm font-semibold">Algo deu errado ao renderizar esta area.</p>
            <p className="text-sm text-muted-foreground">{error.message}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={this.reset}
          className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Tentar novamente
        </button>
      </div>
    );
  }
}
