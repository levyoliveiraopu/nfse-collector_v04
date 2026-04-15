"use client";

import * as React from "react";
import { AlertCircle, CheckCircle2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { formatCnpj, isValidCnpj, normalizeCnpj } from "@/lib/validators/cnpj";

export interface CNPJInputProps
  extends Omit<
    React.InputHTMLAttributes<HTMLInputElement>,
    "value" | "defaultValue" | "onChange" | "type"
  > {
  /** Valor controlado — pode vir mascarado ou so com digitos. */
  value?: string;
  /** Valor inicial (nao controlado). */
  defaultValue?: string;
  /**
   * Emitido quando o usuario digita. Recebe o CNPJ **normalizado**
   * (so digitos, sem mascara) — use esse valor para persistencia.
   */
  onChange?: (normalized: string) => void;
  /**
   * Emitido sempre que a validade muda. Disparado no blur e quando o
   * input atinge 14 digitos. `null` = indeterminado (vazio/incompleto).
   */
  onValidityChange?: (valid: boolean | null) => void;
  /** Sobrescreve a mensagem de erro padrao quando `valid === false`. */
  errorMessage?: string;
  /** Exibe check verde quando valido. Default: true. */
  showValidIcon?: boolean;
  /** Id do label externo para `aria-labelledby`. */
  "aria-labelledby"?: string;
}

const DEFAULT_ERROR = "CNPJ invalido. Verifique os digitos.";

/**
 * CNPJInput (DS-07) — input mascarado `00.000.000/0000-00` com
 * validacao de digito verificador no blur. Emite sempre o valor
 * normalizado (so digitos) via `onChange` para facilitar integracao
 * com forms e APIs.
 */
export const CNPJInput = React.forwardRef<HTMLInputElement, CNPJInputProps>(
  function CNPJInput(
    {
      value,
      defaultValue,
      onChange,
      onValidityChange,
      onBlur,
      errorMessage,
      showValidIcon = true,
      className,
      id,
      disabled,
      readOnly,
      required,
      "aria-describedby": ariaDescribedBy,
      ...rest
    },
    ref,
  ) {
    const isControlled = value !== undefined;
    const [internal, setInternal] = React.useState<string>(() =>
      formatCnpj(defaultValue ?? ""),
    );
    const [touched, setTouched] = React.useState(false);

    const displayRaw = isControlled ? (value ?? "") : internal;
    const display = formatCnpj(displayRaw);
    const normalized = normalizeCnpj(display);
    const complete = normalized.length === 14;
    const valid = complete ? isValidCnpj(normalized) : null;

    const showError = (touched || complete) && valid === false;
    const showSuccess = showValidIcon && valid === true;

    const errorId = `${id ?? "cnpj"}-error`;
    const describedBy = [ariaDescribedBy, showError ? errorId : null]
      .filter(Boolean)
      .join(" ") || undefined;

    // Emite `onValidityChange` apenas quando o valor normalizado muda.
    const lastValidityRef = React.useRef<boolean | null>(null);
    React.useEffect(() => {
      if (lastValidityRef.current !== valid) {
        lastValidityRef.current = valid;
        onValidityChange?.(valid);
      }
    }, [valid, onValidityChange]);

    const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
      const formatted = formatCnpj(event.target.value);
      if (!isControlled) setInternal(formatted);
      onChange?.(normalizeCnpj(formatted));
    };

    const handleBlur = (event: React.FocusEvent<HTMLInputElement>) => {
      setTouched(true);
      onBlur?.(event);
    };

    return (
      <div className={cn("flex flex-col gap-1", className)}>
        <div className="relative">
          <input
            ref={ref}
            id={id}
            type="text"
            inputMode="numeric"
            autoComplete="off"
            spellCheck={false}
            maxLength={18} // 14 digitos + 2 pontos + 1 barra + 1 traco
            placeholder="00.000.000/0000-00"
            value={display}
            onChange={handleChange}
            onBlur={handleBlur}
            disabled={disabled}
            readOnly={readOnly}
            required={required}
            aria-invalid={showError || undefined}
            aria-describedby={describedBy}
            data-state={
              showError ? "invalid" : showSuccess ? "valid" : "idle"
            }
            className={cn(
              "h-9 w-full rounded-md border bg-background px-3 pr-9 text-sm shadow-sm transition",
              "placeholder:text-muted-foreground",
              "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              "disabled:cursor-not-allowed disabled:opacity-60",
              showError
                ? "border-destructive/70 focus-visible:ring-destructive"
                : showSuccess
                  ? "border-success/60"
                  : "border-input",
            )}
            {...rest}
          />
          {showSuccess ? (
            <CheckCircle2
              aria-hidden="true"
              className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-success"
            />
          ) : showError ? (
            <AlertCircle
              aria-hidden="true"
              className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-destructive"
            />
          ) : null}
        </div>
        {showError ? (
          <p
            id={errorId}
            role="alert"
            className="text-xs text-destructive"
          >
            {errorMessage ?? DEFAULT_ERROR}
          </p>
        ) : null}
      </div>
    );
  },
);
