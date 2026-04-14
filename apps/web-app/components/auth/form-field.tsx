import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type FormFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
  description?: string;
};

/**
 * Campo de formulario com label + input + mensagem de erro. Usado apenas
 * nas paginas de auth (nao generalizado em `components/ui/`).
 */
export const FormField = forwardRef<HTMLInputElement, FormFieldProps>(
  function FormField({ label, error, description, id, className, ...props }, ref) {
    const fieldId = id ?? props.name;
    const errorId = error ? `${fieldId}-error` : undefined;
    const descriptionId = description ? `${fieldId}-description` : undefined;
    return (
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor={fieldId}
          className="text-sm font-medium text-foreground"
        >
          {label}
        </label>
        <input
          ref={ref}
          id={fieldId}
          aria-invalid={error ? "true" : undefined}
          aria-describedby={
            [errorId, descriptionId].filter(Boolean).join(" ") || undefined
          }
          className={cn(
            "h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm",
            "placeholder:text-muted-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            "disabled:cursor-not-allowed disabled:opacity-60",
            error && "border-destructive focus-visible:ring-destructive",
            className,
          )}
          {...props}
        />
        {description ? (
          <p id={descriptionId} className="text-xs text-muted-foreground">
            {description}
          </p>
        ) : null}
        {error ? (
          <p id={errorId} className="text-xs text-destructive">
            {error}
          </p>
        ) : null}
      </div>
    );
  },
);
