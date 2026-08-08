"use client";

/**
 * CredentialUploadDialog (APP-04) — dialog com `FileDropzone` + `SecretField`
 * para upload de PFX A1. Traduz erros da API para feedback acionavel.
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
import { FileDropzone } from "@/components/ui/file-dropzone";
import { SecretField } from "@/components/ui/secret-field";
import {
  CredentialApiError,
  type Credential,
  type CredentialErrorCode,
} from "@/lib/companies/credentials";

export interface CredentialUploadDialogProps {
  open: boolean;
  onClose: () => void;
  /**
   * Executor da chamada. O componente fica agnostico da camada HTTP —
   * testes injetam um stub e a pagina injeta `uploadCredential` curried
   * com o accessToken.
   */
  onUpload: (input: { file: File; password: string }) => Promise<Credential>;
  /** Notifica o container quando o upload retornou. */
  onUploaded?: (credential: Credential) => void;
}

const PFX_ACCEPT =
  ".pfx,.p12,application/x-pkcs12,application/pkcs12,application/x-pfx";
const PFX_MAX = 1 * 1024 * 1024; // 1 MiB — alinhado com API_CREDENTIAL_MAX_PFX_BYTES default

function humanizeError(code: CredentialErrorCode, fallback: string): string {
  switch (code) {
    case "invalid_password_or_pfx":
      return "Senha incorreta ou arquivo PFX invalido.";
    case "pfx_too_large":
      return "O arquivo PFX excede o limite aceito pelo servidor (1 MiB).";
    case "pfx_empty":
      return "O arquivo PFX esta vazio.";
    case "pfx_missing_key_or_cert":
      return "O PFX nao contem chave privada e certificado.";
    case "forbidden":
      return "Voce nao tem permissao para atualizar a credencial.";
    case "unauthorized":
      return "Sessao expirada. Faca login novamente.";
    case "storage_failed":
      return "Falha ao gravar no storage. Tente novamente em instantes.";
    case "crypto_failed":
      return "Erro interno ao processar a credencial.";
    case "network":
      return "Falha de rede. Verifique a conexao e tente de novo.";
    default:
      return fallback || "Nao foi possivel enviar a credencial.";
  }
}

export function CredentialUploadDialog({
  open,
  onClose,
  onUpload,
  onUploaded,
}: CredentialUploadDialogProps) {
  const [file, setFile] = React.useState<File | null>(null);
  const [password, setPassword] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Reseta ao fechar.
  React.useEffect(() => {
    if (!open) {
      setFile(null);
      setPassword("");
      setError(null);
      setSubmitting(false);
    }
  }, [open]);

  const handleFile = React.useCallback((picked: File) => {
    setFile(picked);
    setError(null);
  }, []);

  const canSubmit = !!file && password.length > 0 && !submitting;

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file || !password) return;
    setSubmitting(true);
    setError(null);
    try {
      const credential = await onUpload({ file, password });
      onUploaded?.(credential);
      onClose();
    } catch (err) {
      if (err instanceof CredentialApiError) {
        setError(humanizeError(err.code, err.message));
      } else {
        setError(
          err instanceof Error
            ? err.message
            : "Nao foi possivel enviar a credencial.",
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
      labelledBy="credential-upload-title"
      describedBy="credential-upload-desc"
    >
      <DialogHeader>
        <DialogTitle id="credential-upload-title">
          Atualizar credencial A1
        </DialogTitle>
        <DialogDescription id="credential-upload-desc">
          Envie o arquivo <code className="font-mono">.pfx</code> do
          certificado A1 e informe a senha. A credencial anterior sera
          revogada automaticamente.
        </DialogDescription>
      </DialogHeader>
      <form onSubmit={handleSubmit}>
        <DialogBody>
          <FileDropzone
            accept={PFX_ACCEPT}
            maxSize={PFX_MAX}
            onUpload={handleFile}
            label="Arraste o PFX ou clique para selecionar"
            hint="Somente .pfx ou .p12 — ate 1 MB"
            disabled={submitting}
          />
          <div className="flex flex-col gap-1">
            <label
              htmlFor="pfx-password"
              className="text-xs font-medium text-foreground"
            >
              Senha do PFX
            </label>
            <SecretField
              id="pfx-password"
              aria-describedby="credential-security-help"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Digite a senha do certificado"
              allowCopy={false}
              disabled={submitting}
              autoFocus
            />
          </div>
          <p id="credential-security-help" className="text-xs text-muted-foreground">
            A senha é usada somente para validar e cifrar a credencial. Não a
            registre em observações, chamados ou mensagens.
          </p>
          {error ? (
            <p
              role="alert"
              className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive"
              data-testid="credential-upload-error"
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
            className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:bg-primary/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? (
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
            ) : null}
            Enviar credencial
          </button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
