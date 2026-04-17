"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ChevronLeft, RefreshCw } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError } from "@/lib/auth/api-client";
import {
  acknowledgeOccurrence,
  assignOccurrence,
  getOccurrence,
  isTerminal,
  OCCURRENCE_SEVERITY_LABEL,
  OCCURRENCE_STATUS_LABEL,
  resolveOccurrence,
  type Occurrence,
} from "@/lib/api/occurrences";
import { codeLabel, getCodeInfo } from "@/lib/occurrences/codes";

import { OCORRENCIAS_QUERY_KEY } from "../ocorrencias-table";
import { severityVariant, statusVariant } from "../ocorrencias-table";
import { ResolveDialog } from "./resolve-dialog";
import { AssignDialog } from "./assign-dialog";
import { RunbookPanel } from "./runbook-panel";

const WRITE_ROLES = new Set(["owner", "admin", "operator"]);

function detailQueryKey(id: string): [string, string] {
  return ["ocorrencias:detail", id];
}

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export interface OccurrenceDetailViewProps {
  occurrenceId: string;
}

export function OccurrenceDetailView({
  occurrenceId,
}: OccurrenceDetailViewProps) {
  const { accessToken, refresh, user } = useAuth();
  const queryClient = useQueryClient();
  const canWrite = user ? WRITE_ROLES.has(user.role) : false;

  const [resolveOpen, setResolveOpen] = React.useState(false);
  const [assignOpen, setAssignOpen] = React.useState(false);

  const ctx = React.useMemo(
    () => ({
      accessToken,
      onTokenRefreshed: () => {
        void refresh();
      },
    }),
    [accessToken, refresh],
  );

  const query = useQuery<Occurrence, ApiError>({
    queryKey: detailQueryKey(occurrenceId),
    queryFn: () => getOccurrence(occurrenceId, ctx),
    retry: (failureCount, error) => {
      if (
        error instanceof ApiError &&
        error.status >= 400 &&
        error.status < 500
      ) {
        return false;
      }
      return failureCount < 2;
    },
  });

  const invalidateCaches = React.useCallback(
    (updated: Occurrence) => {
      queryClient.setQueryData(detailQueryKey(occurrenceId), updated);
      void queryClient.invalidateQueries({ queryKey: [OCORRENCIAS_QUERY_KEY] });
    },
    [queryClient, occurrenceId],
  );

  const ackMutation = useMutation<Occurrence, ApiError, void>({
    mutationFn: () => acknowledgeOccurrence(occurrenceId, ctx),
    onSuccess: invalidateCaches,
  });

  const resolveMutation = useMutation<Occurrence, ApiError, string>({
    mutationFn: (note: string) =>
      resolveOccurrence(occurrenceId, { note }, ctx),
    onSuccess: (updated) => {
      invalidateCaches(updated);
      setResolveOpen(false);
    },
  });

  const assignMutation = useMutation<Occurrence, ApiError, string>({
    mutationFn: (assigneeId: string) =>
      assignOccurrence(occurrenceId, { assignee_user_id: assigneeId }, ctx),
    onSuccess: (updated) => {
      invalidateCaches(updated);
      setAssignOpen(false);
    },
  });

  return (
    <div className="flex flex-col gap-6">
      <Link
        href="/ocorrencias"
        className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Voltar para ocorrencias
      </Link>

      {query.isPending ? (
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
          Carregando ocorrencia...
        </div>
      ) : query.isError ? (
        <DetailError error={query.error} />
      ) : (
        <>
          <header className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="font-mono text-xs uppercase tracking-tight text-muted-foreground">
                {query.data.code}
              </p>
              <h1 className="text-2xl font-semibold tracking-tight">
                {query.data.title}
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {codeLabel(query.data.code)}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge
                variant={severityVariant(query.data.severity)}
                label={OCCURRENCE_SEVERITY_LABEL[query.data.severity]}
                size="sm"
              />
              <StatusBadge
                variant={statusVariant(query.data.status)}
                label={OCCURRENCE_STATUS_LABEL[query.data.status]}
                size="sm"
              />
            </div>
          </header>

          <section
            aria-label="Detalhes"
            className="rounded-lg border border-border bg-card p-5 text-sm shadow-sm"
          >
            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
              <DlRow label="Empresa">
                <Link
                  href={`/empresas/${query.data.company_id}`}
                  className="font-mono text-xs text-primary hover:underline"
                >
                  {query.data.company_id}
                </Link>
              </DlRow>
              <DlRow label="Execucao">
                {query.data.execution_id ? (
                  <span className="font-mono text-xs">
                    {query.data.execution_id}
                  </span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </DlRow>
              <DlRow label="Primeira ocorrencia">
                {formatDateTime(query.data.first_seen_at)}
              </DlRow>
              <DlRow label="Ultima ocorrencia">
                {formatDateTime(query.data.last_seen_at)}
              </DlRow>
              <DlRow label="Resolvida em">
                {formatDateTime(query.data.resolved_at)}
              </DlRow>
              <DlRow label="Responsavel">
                {query.data.assignee_user_id ? (
                  <span className="font-mono text-xs">
                    {query.data.assignee_user_id}
                  </span>
                ) : (
                  <span className="text-muted-foreground">
                    Nao atribuida
                  </span>
                )}
              </DlRow>
            </dl>
            {query.data.detail ? (
              <div className="mt-4 rounded-md border border-dashed border-border bg-muted/30 p-3 text-xs text-muted-foreground">
                <p className="mb-1 font-medium text-foreground">Detalhe</p>
                <pre className="whitespace-pre-wrap break-words font-mono text-[11px]">
                  {query.data.detail}
                </pre>
              </div>
            ) : null}
          </section>

          {canWrite ? (
            <section
              aria-label="Acoes"
              className="flex flex-wrap items-center gap-2"
              data-section="actions"
            >
              {isTerminal(query.data.status) ? null : (
                <>
                  {query.data.status === "open" ? (
                    <button
                      type="button"
                      onClick={() => ackMutation.mutate()}
                      disabled={ackMutation.isPending}
                      className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border bg-background px-3 text-sm font-medium shadow-sm transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
                    >
                      {ackMutation.isPending
                        ? "Reconhecendo..."
                        : "Reconhecer"}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => setResolveOpen(true)}
                    className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    Resolver
                  </button>
                </>
              )}
              <button
                type="button"
                onClick={() => setAssignOpen(true)}
                className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border bg-background px-3 text-sm font-medium shadow-sm transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                Atribuir
              </button>
              <Link
                href={{
                  pathname: "/execucoes/nova",
                  query: {
                    reprocessar_de: query.data.id,
                    company_id: query.data.company_id,
                  },
                }}
                className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border bg-background px-3 text-sm font-medium shadow-sm transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                title="Abre /execucoes/nova com empresa e contexto pre-preenchidos (APP-05)."
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                Reprocessar
              </Link>
            </section>
          ) : null}

          {ackMutation.isError ? (
            <ActionError error={ackMutation.error} action="acknowledge" />
          ) : null}
          {assignMutation.isError ? (
            <ActionError error={assignMutation.error} action="assign" />
          ) : null}

          <RunbookPanel
            slug={getCodeInfo(query.data.code)?.runbookSlug ?? null}
            code={query.data.code}
          />
        </>
      )}

      <ResolveDialog
        open={resolveOpen}
        onClose={() => setResolveOpen(false)}
        onSubmit={(note) => resolveMutation.mutate(note)}
        pending={resolveMutation.isPending}
        error={resolveMutation.error}
      />
      <AssignDialog
        open={assignOpen}
        onClose={() => setAssignOpen(false)}
        onSubmit={(assigneeId) => assignMutation.mutate(assigneeId)}
        pending={assignMutation.isPending}
        error={assignMutation.error}
      />
    </div>
  );
}

function DlRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs uppercase tracking-tight text-muted-foreground">
        {label}
      </dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

function DetailError({ error }: { error: ApiError | Error }) {
  const isApi = error instanceof ApiError;
  const status = isApi ? error.status : null;
  const message =
    status === 404
      ? "Ocorrencia nao encontrada ou foi removida."
      : status === 403
        ? "Voce nao tem permissao para acessar esta ocorrencia."
        : "Nao foi possivel carregar a ocorrencia.";
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

function ActionError({
  error,
  action,
}: {
  error: ApiError | Error | null;
  action: string;
}) {
  if (!error) return null;
  const isApi = error instanceof ApiError;
  const status = isApi ? error.status : null;
  let message: string;
  if (status === 409) {
    message =
      "A ocorrencia ja esta em um estado terminal — atualize a pagina para ver o status atual.";
  } else if (status === 403) {
    message = "Voce nao tem permissao para executar esta acao.";
  } else if (status === 404) {
    message = "Registro nao encontrado (pode ter sido movido ou removido).";
  } else {
    message = `Nao foi possivel concluir a acao "${action}".`;
  }
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
