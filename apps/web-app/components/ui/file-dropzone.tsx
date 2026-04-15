"use client";

import * as React from "react";
import { AlertCircle, Loader2, Upload } from "lucide-react";

import { cn } from "@/lib/utils";

export type FileDropzoneStatus =
  | "idle"
  | "hover"
  | "uploading"
  | "success"
  | "error";

export interface FileDropzoneProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "onError"> {
  /**
   * Lista de extensoes (`.pfx`, `.p12`) ou MIME types aceitos, separados
   * por virgula. Mesmo formato do atributo `accept` do input nativo.
   */
  accept?: string;
  /** Tamanho maximo em bytes. Default: 5 MB. */
  maxSize?: number;
  /**
   * Callback disparado com o arquivo selecionado. Pode ser async; o
   * componente mostra estado `uploading` enquanto a promise nao resolve.
   */
  onUpload: (file: File) => void | Promise<void>;
  /** Texto principal da zona. */
  label?: string;
  /** Texto de instrucao secundaria (ex.: "PFX ate 5 MB"). */
  hint?: string;
  /** Desabilita o dropzone. */
  disabled?: boolean;
}

const DEFAULT_MAX_SIZE = 5 * 1024 * 1024;

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Retorna `true` se o arquivo corresponder a pelo menos um item da lista
 * de `accept`. Suporta extensoes (`.pfx`), MIME exato
 * (`application/x-pkcs12`) e wildcards (`image/*`).
 */
export function acceptsFile(file: File, accept: string | undefined): boolean {
  if (!accept) return true;
  const tokens = accept
    .split(",")
    .map((t) => t.trim().toLowerCase())
    .filter(Boolean);
  if (tokens.length === 0) return true;
  const name = file.name.toLowerCase();
  const mime = (file.type || "").toLowerCase();
  return tokens.some((token) => {
    if (token.startsWith(".")) return name.endsWith(token);
    if (token.endsWith("/*")) {
      const prefix = token.slice(0, -1); // "image/"
      return mime.startsWith(prefix);
    }
    return mime === token;
  });
}

interface ValidationError {
  kind: "size" | "type";
  message: string;
}

function validate(
  file: File,
  accept: string | undefined,
  maxSize: number,
): ValidationError | null {
  if (!acceptsFile(file, accept)) {
    return {
      kind: "type",
      message: accept
        ? `Tipo nao suportado. Esperado: ${accept}.`
        : "Tipo de arquivo nao suportado.",
    };
  }
  if (file.size > maxSize) {
    return {
      kind: "size",
      message: `Arquivo excede o limite de ${formatBytes(maxSize)}.`,
    };
  }
  return null;
}

/**
 * FileDropzone (DS-07) — drag&drop + clique para selecionar. Valida
 * `accept` (extensao/MIME) e `maxSize` antes de chamar `onUpload`.
 * Usado no upload de PFX A1 (APP-04).
 */
export const FileDropzone = React.forwardRef<HTMLDivElement, FileDropzoneProps>(
  function FileDropzone(
    {
      accept,
      maxSize = DEFAULT_MAX_SIZE,
      onUpload,
      label = "Arraste um arquivo ou clique para selecionar",
      hint,
      disabled = false,
      className,
      ...rest
    },
    ref,
  ) {
    const inputRef = React.useRef<HTMLInputElement>(null);
    const [status, setStatus] = React.useState<FileDropzoneStatus>("idle");
    const [file, setFile] = React.useState<File | null>(null);
    const [error, setError] = React.useState<string | null>(null);

    const handleFiles = React.useCallback(
      async (files: FileList | File[] | null) => {
        if (!files || (files as FileList).length === 0) return;
        const list = Array.from(files as ArrayLike<File>);
        const picked = list[0];
        if (!picked) return;
        const problem = validate(picked, accept, maxSize);
        if (problem) {
          setError(problem.message);
          setStatus("error");
          setFile(null);
          return;
        }
        setError(null);
        setFile(picked);
        setStatus("uploading");
        try {
          await onUpload(picked);
          setStatus("success");
        } catch (err) {
          setStatus("error");
          setError(
            err instanceof Error
              ? err.message
              : "Falha ao enviar o arquivo.",
          );
        }
      },
      [accept, maxSize, onUpload],
    );

    const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
      if (disabled) return;
      event.preventDefault();
      setStatus((s) =>
        s === "uploading" || s === "success" ? s : "hover",
      );
    };

    const handleDragLeave = (event: React.DragEvent<HTMLDivElement>) => {
      if (disabled) return;
      event.preventDefault();
      setStatus((s) => (s === "hover" ? "idle" : s));
    };

    const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
      if (disabled) return;
      event.preventDefault();
      void handleFiles(event.dataTransfer?.files ?? null);
    };

    const openPicker = () => {
      if (disabled) return;
      inputRef.current?.click();
    };

    const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (disabled) return;
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openPicker();
      }
    };

    const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
      void handleFiles(event.target.files);
      // Permite re-selecionar o mesmo arquivo em seguida.
      event.target.value = "";
    };

    const stateClasses =
      status === "error"
        ? "border-destructive/70 bg-destructive/5"
        : status === "hover"
          ? "border-primary bg-primary/5"
          : status === "success"
            ? "border-success/60 bg-success/5"
            : "border-dashed border-input";

    return (
      <div className={cn("flex flex-col gap-2", className)}>
        <div
          ref={ref}
          role="button"
          tabIndex={disabled ? -1 : 0}
          aria-disabled={disabled || undefined}
          aria-label={label}
          data-status={status}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={openPicker}
          onKeyDown={handleKeyDown}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 p-6 text-center transition",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            disabled && "cursor-not-allowed opacity-60",
            stateClasses,
          )}
          {...rest}
        >
          {status === "uploading" ? (
            <Loader2
              aria-hidden="true"
              className="h-6 w-6 animate-spin text-primary"
            />
          ) : status === "error" ? (
            <AlertCircle
              aria-hidden="true"
              className="h-6 w-6 text-destructive"
            />
          ) : (
            <Upload
              aria-hidden="true"
              className="h-6 w-6 text-muted-foreground"
            />
          )}
          <p className="text-sm font-medium text-foreground">{label}</p>
          {hint ? (
            <p className="text-xs text-muted-foreground">{hint}</p>
          ) : null}
          {file && status !== "error" ? (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{file.name}</span>{" "}
              — {formatBytes(file.size)}
            </p>
          ) : null}
          <input
            ref={inputRef}
            type="file"
            accept={accept}
            onChange={handleInputChange}
            className="sr-only"
            tabIndex={-1}
            disabled={disabled}
          />
        </div>
        {error ? (
          <p role="alert" className="text-xs text-destructive">
            {error}
          </p>
        ) : null}
      </div>
    );
  },
);
