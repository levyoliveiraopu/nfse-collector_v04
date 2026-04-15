"use client";

import * as React from "react";
import { Check, Copy, Eye, EyeOff } from "lucide-react";

import { cn } from "@/lib/utils";

export interface SecretFieldProps
  extends Omit<
    React.InputHTMLAttributes<HTMLInputElement>,
    "type" | "value" | "defaultValue" | "onCopy"
  > {
  value?: string;
  defaultValue?: string;
  /** Permitir copiar o valor. Default: true. */
  allowCopy?: boolean;
  /** Permitir alternar mostrar/ocultar. Default: true. */
  allowReveal?: boolean;
  /** Rotulo acessivel do botao mostrar/ocultar. */
  revealLabel?: string;
  /** Rotulo acessivel do botao copiar. */
  copyLabel?: string;
  /** Duracao (ms) do flash "Copiado!". Default 1500. */
  copyFeedbackMs?: number;
  /** Callback chamado apos copia bem-sucedida. */
  onCopy?: (value: string) => void;
  /** Callback chamado se a copia falhar. */
  onCopyError?: (error: unknown) => void;
}

async function copyToClipboard(value: string): Promise<void> {
  if (
    typeof navigator !== "undefined" &&
    navigator.clipboard?.writeText
  ) {
    await navigator.clipboard.writeText(value);
    return;
  }
  // Fallback para ambientes sem Clipboard API (ex.: http sem HTTPS).
  if (typeof document === "undefined") {
    throw new Error("clipboard unavailable");
  }
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  try {
    const ok = document.execCommand?.("copy");
    if (!ok) throw new Error("execCommand returned false");
  } finally {
    document.body.removeChild(textarea);
  }
}

/**
 * SecretField (DS-07) — input type="password" com botoes para
 * mostrar/ocultar e copiar o valor. Pensado para senhas de PFX,
 * tokens de API e outros segredos.
 */
export const SecretField = React.forwardRef<HTMLInputElement, SecretFieldProps>(
  function SecretField(
    {
      value,
      defaultValue,
      allowCopy = true,
      allowReveal = true,
      revealLabel,
      copyLabel = "Copiar",
      copyFeedbackMs = 1500,
      onCopy,
      onCopyError,
      onChange,
      className,
      disabled,
      readOnly,
      id,
      ...rest
    },
    ref,
  ) {
    const isControlled = value !== undefined;
    const [internal, setInternal] = React.useState<string>(
      () => defaultValue ?? "",
    );
    const [revealed, setRevealed] = React.useState(false);
    const [copied, setCopied] = React.useState(false);
    const copyTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);

    const current = isControlled ? (value ?? "") : internal;
    const hasValue = current.length > 0;

    React.useEffect(() => {
      return () => {
        if (copyTimer.current) clearTimeout(copyTimer.current);
      };
    }, []);

    const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
      if (!isControlled) setInternal(event.target.value);
      onChange?.(event);
    };

    const handleReveal = () => setRevealed((v) => !v);

    const handleCopy = async () => {
      try {
        await copyToClipboard(current);
        setCopied(true);
        onCopy?.(current);
        if (copyTimer.current) clearTimeout(copyTimer.current);
        copyTimer.current = setTimeout(
          () => setCopied(false),
          copyFeedbackMs,
        );
      } catch (error) {
        onCopyError?.(error);
      }
    };

    const revealBtnLabel =
      revealLabel ?? (revealed ? "Ocultar" : "Mostrar");

    return (
      <div className={cn("flex flex-col gap-1", className)}>
        <div className="relative">
          <input
            ref={ref}
            id={id}
            type={revealed ? "text" : "password"}
            autoComplete="off"
            spellCheck={false}
            value={current}
            onChange={handleChange}
            disabled={disabled}
            readOnly={readOnly}
            className={cn(
              "h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm transition",
              "placeholder:text-muted-foreground",
              "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              "disabled:cursor-not-allowed disabled:opacity-60",
              allowReveal && allowCopy
                ? "pr-20"
                : allowReveal || allowCopy
                  ? "pr-11"
                  : "pr-3",
            )}
            {...rest}
          />
          <div className="absolute right-1 top-1/2 flex -translate-y-1/2 items-center gap-0.5">
            {allowReveal ? (
              <button
                type="button"
                onClick={handleReveal}
                aria-label={revealBtnLabel}
                aria-pressed={revealed}
                title={revealBtnLabel}
                disabled={disabled}
                className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition hover:bg-accent hover:text-accent-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
              >
                {revealed ? (
                  <EyeOff aria-hidden="true" className="h-4 w-4" />
                ) : (
                  <Eye aria-hidden="true" className="h-4 w-4" />
                )}
              </button>
            ) : null}
            {allowCopy ? (
              <button
                type="button"
                onClick={handleCopy}
                aria-label={copied ? "Copiado" : copyLabel}
                title={copied ? "Copiado!" : copyLabel}
                disabled={disabled || !hasValue}
                className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition hover:bg-accent hover:text-accent-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
              >
                {copied ? (
                  <Check
                    aria-hidden="true"
                    className="h-4 w-4 text-success"
                  />
                ) : (
                  <Copy aria-hidden="true" className="h-4 w-4" />
                )}
              </button>
            ) : null}
          </div>
        </div>
        {copied ? (
          <p
            role="status"
            aria-live="polite"
            className="text-xs text-success"
          >
            Copiado para a area de transferencia
          </p>
        ) : null}
      </div>
    );
  },
);
