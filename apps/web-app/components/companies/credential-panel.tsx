"use client";

/**
 * CredentialPanel (APP-04) — aba "Credencial" de `/empresas/[id]`.
 *
 * Orquestra leitura da credencial ativa, upload (FileDropzone +
 * SecretField), "Testar agora" e revogacao (ConfirmDialog "digite
 * REVOGAR"). "Testar agora" fica desabilitado ate entregarmos o
 * endpoint de handshake real (sub-issue).
 */
import * as React from "react";
import { Loader2, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { CredentialStatusBlock } from "./credential-status-block";
import { CredentialUploadDialog } from "./credential-upload-dialog";
import { CredentialRevokeDialog } from "./credential-revoke-dialog";
import {
  CredentialApiError,
  type Credential,
  fetchCredential,
  revokeCredential,
  uploadCredential,
} from "@/lib/companies/credentials";

export interface CredentialPanelProps {
  companyId: string;
  /** Overrides opcionais para testes. */
  clientOverrides?: {
    fetch?: typeof fetchCredential;
    upload?: typeof uploadCredential;
    revoke?: typeof revokeCredential;
  };
}

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; credential: Credential | null }
  | { kind: "error"; message: string };

export function CredentialPanel({
  companyId,
  clientOverrides,
}: CredentialPanelProps) {
  const { accessToken, status: authStatus, user } = useAuth();
  const fetchFn = clientOverrides?.fetch ?? fetchCredential;
  const uploadFn = clientOverrides?.upload ?? uploadCredential;
  const revokeFn = clientOverrides?.revoke ?? revokeCredential;

  const [state, setState] = React.useState<LoadState>({ kind: "loading" });
  const [uploadOpen, setUploadOpen] = React.useState(false);
  const [revokeOpen, setRevokeOpen] = React.useState(false);
  const [cnMismatchSignal, setCnMismatchSignal] = React.useState(false);
  const [flash, setFlash] = React.useState<string | null>(null);

  const role = user?.role ?? null;
  const canWrite = role === "owner" || role === "admin";

  const load = React.useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const credential = await fetchFn(companyId, {
        accessToken,
      });
      setState({ kind: "ready", credential });
    } catch (err) {
      const message =
        err instanceof CredentialApiError
          ? err.message
          : "Falha ao carregar credencial.";
      setState({ kind: "error", message });
    }
  }, [companyId, accessToken, fetchFn]);

  React.useEffect(() => {
    // So consulta quando a sessao ja esta autenticada — evita um
    // 401 espurio durante a rehidratacao do AuthProvider.
    if (authStatus !== "authenticated") return;
    void load();
  }, [load, authStatus]);

  const handleUploaded = (credential: Credential) => {
    setState({ kind: "ready", credential });
    setCnMismatchSignal(credential.cn_matches_cnpj === false);
    setFlash("Credencial enviada com sucesso.");
  };

  const handleRevoked = () => {
    setState({ kind: "ready", credential: null });
    setCnMismatchSignal(false);
    setFlash("Credencial revogada.");
  };

  const doUpload = React.useCallback(
    ({ file, password }: { file: File; password: string }) =>
      uploadFn(companyId, { file, password }, { accessToken }),
    [companyId, accessToken, uploadFn],
  );

  const doRevoke = React.useCallback(
    () => revokeFn(companyId, { accessToken }),
    [companyId, accessToken, revokeFn],
  );

  return (
    <div className="flex flex-col gap-4" data-help-id="credential-primary">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          Credencial A1
        </h1>
        <p className="text-sm text-muted-foreground">
          Gerencie o certificado digital usado para acessar o portal da
          prefeitura no nome desta empresa.
        </p>
      </header>

      {state.kind === "loading" ? (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-2 rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground"
        >
          <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
          Carregando credencial...
        </div>
      ) : null}

      {state.kind === "error" ? (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive"
        >
          <span>{state.message}</span>
          <button
            type="button"
            onClick={() => void load()}
            className="inline-flex h-8 items-center justify-center rounded-md border border-destructive/40 bg-background px-3 text-xs font-medium text-destructive transition hover:bg-destructive/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Tentar novamente
          </button>
        </div>
      ) : null}

      {state.kind === "ready" ? (
        <CredentialStatusBlock
          credential={state.credential}
          cnMismatchWarning={cnMismatchSignal}
        />
      ) : null}

      {flash ? (
        <p
          role="status"
          aria-live="polite"
          className="rounded-md border border-success/40 bg-success/10 px-3 py-2 text-xs text-success"
        >
          {flash}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => {
            setFlash(null);
            setUploadOpen(true);
          }}
          disabled={!canWrite || state.kind === "loading"}
          title={
            canWrite
              ? undefined
              : "Somente owner ou admin podem atualizar a credencial."
          }
          className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:bg-primary/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw aria-hidden="true" className="h-4 w-4" />
          Atualizar credencial
        </button>
        <button
          type="button"
          disabled
          title="Disponivel apos integracao com o endpoint de teste de autenticacao."
          className="inline-flex h-9 cursor-not-allowed items-center justify-center gap-2 rounded-md border border-input bg-background px-4 text-sm font-medium text-muted-foreground opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ShieldCheck aria-hidden="true" className="h-4 w-4" />
          Testar agora
        </button>
        <button
          type="button"
          onClick={() => {
            setFlash(null);
            setRevokeOpen(true);
          }}
          disabled={
            !canWrite ||
            state.kind !== "ready" ||
            state.credential === null
          }
          title={
            canWrite
              ? undefined
              : "Somente owner ou admin podem revogar a credencial."
          }
          className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-destructive/40 bg-background px-4 text-sm font-medium text-destructive transition hover:bg-destructive/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Trash2 aria-hidden="true" className="h-4 w-4" />
          Revogar
        </button>
      </div>

      <CredentialUploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUpload={doUpload}
        onUploaded={handleUploaded}
      />
      <CredentialRevokeDialog
        open={revokeOpen}
        onClose={() => setRevokeOpen(false)}
        onRevoke={doRevoke}
        onRevoked={handleRevoked}
      />
    </div>
  );
}
