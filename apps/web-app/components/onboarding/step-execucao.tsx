"use client";

/**
 * Passo 3 do wizard (APP-11): disparar a 1a coleta e acompanhar ate o
 * estado terminal. Ao concluir com sucesso ou parcial, dispara o
 * evento `first_collection_done` via `POST /onboarding/first-collection-done`
 * (outbox `notifications`) e libera a tela de "parabens".
 *
 * O periodo padrao sao os ultimos 30 dias (em UTC). Nao expomos
 * PeriodPicker: o wizard deve ser o mais curto possivel — a pagina
 * `/execucoes/nova` cobre configuracao avancada.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Loader2, Play } from "lucide-react";
import Link from "next/link";

import { useAuth } from "@/components/auth/auth-provider";
import { formatCnpj, type Company } from "@/lib/api/companies";
import {
  createExecutions,
  ExecutionsApiError,
  getExecution,
  isTerminalStatus,
  type CreatedExecution,
  type Execution,
  type ExecutionStatus,
} from "@/lib/api/executions";
import { postFirstCollectionDone } from "@/lib/api/onboarding";

export interface StepExecucaoProps {
  company: Company;
  /**
   * Chamado quando a execucao atinge estado terminal favoravel
   * (`succeeded` ou `partial`). Recebe o status final para UI.
   */
  onCompleted: (status: ExecutionStatus) => void;
}

function last30DaysRange(): { from: string; to: string } {
  const today = new Date();
  const to = today.toISOString().slice(0, 10);
  const thirty = new Date(today);
  thirty.setUTCDate(thirty.getUTCDate() - 30);
  const from = thirty.toISOString().slice(0, 10);
  return { from, to };
}

export function StepExecucao({ company, onCompleted }: StepExecucaoProps) {
  const { user, accessToken, refresh } = useAuth();
  const role = user?.role ?? "viewer";
  const canTrigger = ["owner", "admin", "operator"].includes(role);

  const ctx = React.useMemo(
    () => ({
      accessToken,
      onTokenRefreshed: () => {
        void refresh();
      },
    }),
    [accessToken, refresh],
  );

  const [triggering, setTriggering] = React.useState(false);
  const [triggerError, setTriggerError] = React.useState<string | null>(null);
  const [executionId, setExecutionId] = React.useState<string | null>(null);
  const [notified, setNotified] = React.useState(false);

  const { from, to } = React.useMemo(last30DaysRange, []);

  async function handleStart() {
    if (!canTrigger) return;
    setTriggering(true);
    setTriggerError(null);
    try {
      const res = await createExecutions(
        {
          company_ids: [company.id],
          period_start: from,
          period_end: to,
          dry_run: false,
          trigger: "manual",
        },
        ctx,
      );
      const created: CreatedExecution | undefined = res.created[0];
      if (!created) {
        throw new Error("resposta vazia do backend");
      }
      if (created.enqueue_error) {
        setTriggerError(
          "Nao foi possivel enfileirar a coleta. Tente novamente em instantes.",
        );
        return;
      }
      setExecutionId(created.execution_id);
    } catch (err) {
      if (err instanceof ExecutionsApiError) {
        if (err.code === "credential_missing_or_expired") {
          setTriggerError(
            "A credencial da empresa nao esta ativa. Volte ao passo 2 e tente de novo.",
          );
        } else if (err.code === "forbidden") {
          setTriggerError(
            "Seu papel nao pode disparar coletas. Peca a um owner/admin/operator.",
          );
        } else if (err.code === "queue_unavailable") {
          setTriggerError(
            "Fila de jobs indisponivel. Tente novamente em instantes.",
          );
        } else {
          setTriggerError(err.message);
        }
      } else {
        setTriggerError("Falha ao iniciar a coleta. Tente novamente.");
      }
    } finally {
      setTriggering(false);
    }
  }

  const detail = useQuery({
    queryKey: ["onboarding", "execution", executionId],
    queryFn: () =>
      executionId ? getExecution(executionId, ctx) : Promise.resolve(null),
    enabled: Boolean(executionId),
    refetchInterval: (query) => {
      const data = query.state.data as Execution | null | undefined;
      if (!data) return 2000;
      return isTerminalStatus(data.status) ? false : 2000;
    },
  });

  const execution = detail.data ?? null;
  const terminal = execution ? isTerminalStatus(execution.status) : false;
  const succeeded =
    terminal &&
    execution &&
    (execution.status === "succeeded" || execution.status === "partial");

  React.useEffect(() => {
    if (!succeeded || notified || !execution) return;
    // Marca primeiro para evitar duplicata em re-renders rapidos.
    setNotified(true);
    void postFirstCollectionDone(ctx)
      .catch(() => {
        // Falha silenciosa: o evento ja foi disparado pelo backend ou
        // cairah em retry quando o wizard reabrir. A UX do passo 3
        // nao bloqueia o usuario por conta do email.
      })
      .finally(() => {
        onCompleted(execution.status);
      });
  }, [succeeded, notified, execution, ctx, onCompleted]);

  const processed =
    execution !== null
      ? execution.items_ok + execution.items_fail
      : 0;
  const total =
    execution !== null ? Math.max(execution.items_total, processed) : 0;
  const percent =
    total === 0 ? 0 : Math.min(100, Math.round((processed / total) * 100));

  if (!canTrigger) {
    return (
      <div
        role="alert"
        className="flex items-start gap-2 rounded-md border border-border bg-card p-4 text-sm"
        data-testid="onboarding-step-execucao"
      >
        <AlertTriangle
          className="mt-0.5 h-4 w-4 text-warning"
          aria-hidden="true"
        />
        <div>
          <p className="font-medium">Sem permissao para iniciar coleta</p>
          <p className="text-muted-foreground">
            Seu papel e <strong>{role}</strong>. Owners, admins e operators
            conseguem disparar. Peca a um deles para completar esta etapa —
            o wizard retoma aqui automaticamente apos a 1a coleta.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex flex-col gap-4"
      data-testid="onboarding-step-execucao"
    >
      <div className="rounded-md border border-border bg-muted/30 p-4 text-sm">
        <p className="font-medium">
          {company.razao_social}{" "}
          <span className="font-mono text-xs text-muted-foreground">
            {formatCnpj(company.cnpj)}
          </span>
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Periodo: <strong>{from}</strong> a <strong>{to}</strong> (ultimos 30 dias).
          Dry-run desligado — os XMLs serao persistidos no storage.
        </p>
      </div>

      {!executionId ? (
        <>
          {triggerError ? (
            <p
              role="alert"
              className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
              data-testid="onb-execucao-error"
            >
              {triggerError}
            </p>
          ) : null}
          <button
            type="button"
            onClick={handleStart}
            disabled={triggering}
            className="inline-flex h-10 items-center justify-center gap-2 self-end rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            data-testid="onb-execucao-start"
          >
            {triggering ? (
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
            ) : (
              <Play aria-hidden="true" className="h-4 w-4" />
            )}
            {triggering ? "Enfileirando…" : "Iniciar 1a coleta"}
          </button>
        </>
      ) : null}

      {executionId && execution ? (
        <section
          aria-label="Progresso da 1a coleta"
          className="flex flex-col gap-3 rounded-md border border-border bg-card p-4"
          data-execution-status={execution.status}
        >
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              Status atual: <strong>{execution.status}</strong>
            </span>
            <span>
              {processed} de {total} itens · {percent}%
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              role="progressbar"
              aria-valuenow={processed}
              aria-valuemin={0}
              aria-valuemax={Math.max(total, 1)}
              aria-label="Progresso da 1a coleta"
              className="h-full bg-primary transition-all"
              style={{ width: `${percent}%` }}
            />
          </div>

          {terminal && succeeded ? (
            <div
              role="status"
              className="flex items-start gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/5 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-400"
              data-testid="onb-execucao-sucesso"
            >
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <div>
                <p className="font-medium">Primeira coleta concluida.</p>
                <p className="text-xs">
                  Um email de confirmacao sera enviado para o responsavel do
                  tenant. Voce ja pode explorar o dashboard.
                </p>
              </div>
            </div>
          ) : null}

          {terminal && !succeeded ? (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <div>
                <p className="font-medium">A coleta terminou em falha.</p>
                <p className="text-xs">
                  Abra a aba <strong>Ocorrencias</strong> ou a pagina da
                  execucao para entender o motivo. Voce pode reiniciar a 1a
                  coleta abaixo assim que resolver.
                </p>
                <div className="mt-2 flex gap-2 text-xs">
                  <Link
                    href={`/execucoes/${execution.id}`}
                    className="underline"
                  >
                    Abrir execucao
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      setExecutionId(null);
                      setNotified(false);
                    }}
                    className="underline"
                  >
                    Tentar novamente
                  </button>
                </div>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
