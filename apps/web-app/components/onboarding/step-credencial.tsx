"use client";

/**
 * Passo 2 do wizard (APP-11): subir o PFX A1 da 1a empresa.
 *
 * Usa os componentes FileDropzone + SecretField diretamente (sem abrir
 * o `<CredentialUploadDialog>` do APP-04 — evitamos modal aninhado). A
 * semantica de erros e copiada/simplificada da mesma funcao
 * `humanizeError` do dialog; acessar via `CredentialApiError` garante
 * traducoes consistentes.
 */
import * as React from "react";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { FileDropzone } from "@/components/ui/file-dropzone";
import { SecretField } from "@/components/ui/secret-field";
import {
  CredentialApiError,
  type CredentialErrorCode,
  uploadCredential,
  type Credential,
} from "@/lib/companies/credentials";

const PFX_ACCEPT =
  ".pfx,.p12,application/x-pkcs12,application/pkcs12,application/x-pfx";
const PFX_MAX = 1 * 1024 * 1024;

function humanize(code: CredentialErrorCode, fallback: string): string {
  switch (code) {
    case "invalid_password_or_pfx":
      return "Senha incorreta ou arquivo PFX invalido.";
    case "pfx_too_large":
      return "O arquivo PFX excede o limite aceito (1 MiB).";
    case "pfx_empty":
      return "O arquivo PFX esta vazio.";
    case "pfx_missing_key_or_cert":
      return "O PFX nao contem chave privada e certificado.";
    case "forbidden":
      return "Voce nao tem permissao para subir credenciais. Peca a um owner/admin.";
    case "unauthorized":
      return "Sessao expirada. Faca login novamente.";
    case "storage_failed":
      return "Falha ao gravar no storage. Tente novamente em instantes.";
    case "crypto_failed":
      return "Erro interno ao processar a credencial.";
    case "network":
      return "Falha de rede. Verifique a conexao.";
    default:
      return fallback || "Nao foi possivel enviar a credencial.";
  }
}

export interface StepCredencialProps {
  companyId: string;
  onUploaded: (credential: Credential) => void;
}

export function StepCredencial({
  companyId,
  onUploaded,
}: StepCredencialProps) {
  const { accessToken, refresh } = useAuth();
  const [file, setFile] = React.useState<File | null>(null);
  const [password, setPassword] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const canSubmit = Boolean(file) && password.length > 0 && !submitting;

  const onFile = React.useCallback((picked: File) => {
    setFile(picked);
    setError(null);
  }, []);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || !password) return;
    setSubmitting(true);
    setError(null);
    try {
      const credential = await uploadCredential(
        companyId,
        { file, password },
        {
          accessToken,
          onTokenRefreshed: () => {
            void refresh();
          },
        },
      );
      onUploaded(credential);
    } catch (err) {
      if (err instanceof CredentialApiError) {
        setError(humanize(err.code, err.message));
      } else {
        setError("Nao foi possivel enviar a credencial.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-4"
      noValidate
      data-testid="onboarding-step-credencial"
    >
      <p className="text-sm text-muted-foreground">
        Envie o arquivo <code className="font-mono">.pfx</code> do certificado
        digital A1 e informe a senha. A credencial fica cifrada em repouso
        (AES-256-GCM) e so e usada para autenticar no portal da prefeitura.
      </p>

      <FileDropzone
        accept={PFX_ACCEPT}
        maxSize={PFX_MAX}
        onUpload={onFile}
        label="Arraste o PFX ou clique para selecionar"
        hint="Somente .pfx ou .p12 — ate 1 MB"
        disabled={submitting}
      />

      <div className="flex flex-col gap-1">
        <label
          htmlFor="onb-pfx-password"
          className="text-xs font-medium text-foreground"
        >
          Senha do PFX
        </label>
        <SecretField
          id="onb-pfx-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Digite a senha do certificado"
          allowCopy={false}
          disabled={submitting}
        />
      </div>

      {error ? (
        <p
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive"
          data-testid="onb-credencial-error"
        >
          {error}
        </p>
      ) : null}

      <div className="flex items-center justify-end">
        <button
          type="submit"
          disabled={!canSubmit}
          className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {submitting ? (
            <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
          ) : null}
          {submitting ? "Enviando…" : "Enviar credencial"}
        </button>
      </div>
    </form>
  );
}
