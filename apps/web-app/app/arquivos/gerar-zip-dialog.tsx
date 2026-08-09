"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Download, Loader2 } from "lucide-react";

import { Modal } from "@/components/ui/modal";
import { PeriodPicker, type PeriodRange } from "@/components/ui/period-picker";
import { useAuth } from "@/components/auth/auth-provider";
import { computePresetRange } from "@/lib/date/period";
import type { Company } from "@/lib/api/companies";
import {
  EXPORT_STATUS_LABEL,
  ExportsApiError,
  createExport,
  getExport,
  isTerminalExportStatus,
  type ExportRecord,
  type ExportKind,
  type ExportStatus,
} from "@/lib/api/exports";

import { FILES_QUERY_KEY } from "./arquivos-view";

export interface GerarZipDialogProps {
  open: boolean;
  onClose: () => void;
  companies: Company[];
  companiesLoading?: boolean;
}

/** Intervalo em ms entre consultas ao `GET /exports/{id}`. */
const POLL_INTERVAL_MS = 3000;
/** Tempo maximo de espera antes de desistir do polling (10 min). */
const POLL_TIMEOUT_MS = 10 * 60 * 1000;

type PhaseState =
  | { phase: "idle" }
  | { phase: "submitting" }
  | { phase: "polling"; exportId: string; status: ExportStatus }
  | { phase: "ready"; record: ExportRecord }
  | { phase: "empty"; record: ExportRecord }
  | { phase: "failed"; message: string }
  | { phase: "timed_out"; exportId: string };

function isInProgress(state: PhaseState): boolean {
  return state.phase === "submitting" || state.phase === "polling";
}

export function GerarZipDialog({
  open,
  onClose,
  companies,
  companiesLoading,
}: GerarZipDialogProps) {
  const { accessToken, refresh } = useAuth();
  const queryClient = useQueryClient();

  const [companyId, setCompanyId] = React.useState("");
  const [kind, setKind] = React.useState<ExportKind>("zip_xml");
  const [period, setPeriod] = React.useState<PeriodRange>(() =>
    computePresetRange("last_30d"),
  );
  const [state, setState] = React.useState<PhaseState>({ phase: "idle" });

  const ctx = React.useMemo(
    () => ({
      accessToken,
      onTokenRefreshed: () => {
        void refresh();
      },
    }),
    [accessToken, refresh],
  );

  // Reset quando abre.
  React.useEffect(() => {
    if (!open) return;
    setCompanyId("");
    setKind("zip_xml");
    setPeriod(computePresetRange("last_30d"));
    setState({ phase: "idle" });
  }, [open]);

  // Polling: dispara quando entra em `polling` e limpa em cleanup.
  React.useEffect(() => {
    if (state.phase !== "polling") return;
    let cancelled = false;
    const startedAt = Date.now();
    const exportId = state.exportId;

    async function tick(): Promise<void> {
      if (cancelled) return;
      try {
        const record = await getExport(exportId, ctx);
        if (cancelled) return;
        if (record.status === "ready") {
          setState({ phase: "ready", record });
          void queryClient.invalidateQueries({ queryKey: [FILES_QUERY_KEY] });
          return;
        }
        if (record.status === "empty") {
          setState({ phase: "empty", record });
          return;
        }
        if (record.status === "failed") {
          setState({
            phase: "failed",
            message:
              record.error_message ??
              "O export falhou durante o processamento.",
          });
          return;
        }
        // queued/running: atualiza status e re-agenda.
        setState((prev) =>
          prev.phase === "polling"
            ? { ...prev, status: record.status }
            : prev,
        );
        if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
          setState({ phase: "timed_out", exportId });
          return;
        }
        window.setTimeout(tick, POLL_INTERVAL_MS);
      } catch (err) {
        if (cancelled) return;
        setState({
          phase: "failed",
          message:
            err instanceof ExportsApiError
              ? err.message
              : "Falha ao consultar status do export.",
        });
      }
    }

    const handle = window.setTimeout(tick, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [state, ctx, queryClient]);

  async function handleSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (!companyId) {
      setState({
        phase: "failed",
        message: "Selecione uma empresa para gerar o arquivo.",
      });
      return;
    }
    setState({ phase: "submitting" });
    try {
      const response = await createExport(
        {
          company_id: companyId,
          period_start: period.from,
          period_end: period.to,
          kind,
        },
        ctx,
      );
      if (response.status === "failed") {
        setState({
          phase: "failed",
          message:
            response.enqueue_error === "enqueue_failed"
              ? "A fila de jobs nao aceitou o pedido. Tente novamente."
              : "Nao foi possivel iniciar o export.",
        });
        return;
      }
      setState({
        phase: "polling",
        exportId: response.export_id,
        status: response.status,
      });
    } catch (err) {
      setState({
        phase: "failed",
        message:
          err instanceof ExportsApiError
            ? err.message
            : "Falha ao criar export.",
      });
    }
  }

  const dismissable = !isInProgress(state);

  return (
    <Modal
      open={open}
      onClose={dismissable ? onClose : () => undefined}
      title="Gerar arquivo fiscal"
      description="Gera os XMLs em ZIP ou uma planilha Excel das NFS-e emitidas."
      dismissable={dismissable}
      maxWidth="max-w-lg"
    >
      {state.phase === "ready" ? (
        <ReadyPanel record={state.record} onClose={onClose} />
      ) : state.phase === "empty" ? (
        <EmptyPanel onClose={onClose} />
      ) : state.phase === "timed_out" ? (
        <TimedOutPanel onClose={onClose} />
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1">
            <label htmlFor="zip-company" className="text-sm font-medium">
              Empresa
            </label>
            <select
              id="zip-company"
              value={companyId}
              onChange={(e) => setCompanyId(e.target.value)}
              disabled={companiesLoading || isInProgress(state)}
              className="h-9 rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="">Selecione uma empresa…</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.razao_social}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-sm font-medium">Periodo</span>
            <PeriodPicker
              value={period}
              onChange={(next) => setPeriod(next)}
              descriptionId="export-period-help"
            />
            <p id="export-period-help" className="text-xs text-muted-foreground">
              O período inclui as duas datas e considera somente notas emitidas
              pela empresa selecionada.
            </p>
          </div>

          <fieldset className="flex flex-col gap-2" aria-describedby="export-format-help">
            <legend className="text-sm font-medium">Formato</legend>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="export-kind"
                value="zip_xml"
                checked={kind === "zip_xml"}
                onChange={() => setKind("zip_xml")}
                disabled={isInProgress(state)}
              />
              ZIP com os XMLs
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="export-kind"
                value="excel_nfse"
                checked={kind === "excel_nfse"}
                onChange={() => setKind("excel_nfse")}
                disabled={isInProgress(state)}
              />
              Excel com notas e resumo
            </label>
            <p id="export-format-help" className="text-xs text-muted-foreground">
              Use Excel para análise e ZIP para obter os XMLs originais. Notas
              canceladas permanecem identificadas no resultado.
            </p>
          </fieldset>

          {state.phase === "failed" ? (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
            >
              <AlertTriangle
                className="mt-0.5 h-4 w-4 shrink-0"
                aria-hidden="true"
              />
              <span>{state.message}</span>
            </div>
          ) : null}

          {state.phase === "polling" ? (
            <div
              role="status"
              aria-live="polite"
              data-testid="export-polling"
              className="flex items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-2 text-sm"
            >
              <Loader2
                className="h-4 w-4 animate-spin"
                aria-hidden="true"
              />
              <span>
                Export em andamento — {EXPORT_STATUS_LABEL[state.status]}…
              </span>
            </div>
          ) : null}

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isInProgress(state)}
              className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium text-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isInProgress(state)}
              className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {state.phase === "submitting" ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  Enviando…
                </>
              ) : (
                "Gerar"
              )}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}

function ReadyPanel({
  record,
  onClose,
}: {
  record: ExportRecord;
  onClose: () => void;
}) {
  const isExcel = record.kind === "excel_nfse";
  return (
    <div className="flex flex-col gap-4" data-testid="export-ready">
      <div className="flex items-start gap-2 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-900 dark:text-emerald-200">
        <CheckCircle2
          className="mt-0.5 h-4 w-4 shrink-0"
          aria-hidden="true"
        />
        <div className="flex flex-col gap-0.5">
          <strong className="font-medium">
            {isExcel ? "Excel pronto para download" : "ZIP pronto para download"}
          </strong>
          <span className="text-xs opacity-90">
            {record.items_count} nota{record.items_count === 1 ? "" : "s"}{" "}
            emitida{record.items_count === 1 ? "" : "s"}. A URL expira em 1 hora.
          </span>
        </div>
      </div>
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onClose}
          className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium text-foreground transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Fechar
        </button>
        {record.download_url ? (
          <a
            href={record.download_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            {isExcel ? "Baixar Excel" : "Baixar ZIP"}
          </a>
        ) : null}
      </div>
    </div>
  );
}

function EmptyPanel({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex flex-col gap-4" data-testid="export-empty">
      <p className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm">
        Nenhuma NFS-e emitida foi encontrada para essa empresa e periodo.
        Nenhum arquivo foi gerado.
      </p>
      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={onClose}
          className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium text-foreground transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Fechar
        </button>
      </div>
    </div>
  );
}

function TimedOutPanel({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex flex-col gap-4" data-testid="export-timed-out">
      <div
        role="alert"
        className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-900 dark:text-amber-200"
      >
        <AlertTriangle
          className="mt-0.5 h-4 w-4 shrink-0"
          aria-hidden="true"
        />
        <span>
          O export ainda esta em andamento. Feche esta janela e atualize a
          pagina em alguns minutos — o arquivo aparecera na listagem quando
          ficar pronto.
        </span>
      </div>
      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={onClose}
          className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium text-foreground transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Fechar
        </button>
      </div>
    </div>
  );
}
