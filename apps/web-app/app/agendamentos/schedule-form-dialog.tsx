"use client";

import * as React from "react";
import { AlertTriangle, CalendarClock } from "lucide-react";

import { Modal } from "@/components/ui/modal";
import { useAuth } from "@/components/auth/auth-provider";
import { ApiError } from "@/lib/auth/api-client";
import {
  createSchedule,
  extractErrorDetail,
  updateSchedule,
  type Schedule,
  type SchedulePreset,
} from "@/lib/api/schedules";
import type { Company } from "@/lib/api/companies";
import {
  builderToCron,
  computeNextRuns,
  cronToBuilder,
  CronParseError,
  DOW_LABEL_PT,
  validateCron,
  type BuilderMode,
  type BuilderValue,
} from "@/lib/schedules/cron";

const DEFAULT_TZ = "America/Sao_Paulo";
const TZ_OPTIONS = [
  "America/Sao_Paulo",
  "America/Fortaleza",
  "America/Manaus",
  "America/Rio_Branco",
  "America/Noronha",
  "UTC",
];

export interface ScheduleFormDialogProps {
  open: boolean;
  onClose: () => void;
  onSaved: (schedule: Schedule) => void;
  editing: Schedule | null;
  presets: SchedulePreset[];
  companies: Company[];
  companiesLoading?: boolean;
}

type FormState = {
  companyId: string;
  timezone: string;
  enabled: boolean;
  builder: BuilderValue;
};

function makeDefaultState(editing: Schedule | null): FormState {
  if (editing) {
    return {
      companyId: editing.company_id ?? "",
      timezone: editing.timezone,
      enabled: editing.enabled,
      builder: cronToBuilder(editing.cron_expr),
    };
  }
  return {
    companyId: "",
    timezone: DEFAULT_TZ,
    enabled: true,
    builder: { mode: "daily", hour: 3, minute: 0 },
  };
}

function formatRun(date: Date, tz: string): string {
  try {
    return date.toLocaleString("pt-BR", {
      timeZone: tz,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return date.toISOString();
  }
}

export function ScheduleFormDialog({
  open,
  onClose,
  onSaved,
  editing,
  presets,
  companies,
  companiesLoading,
}: ScheduleFormDialogProps) {
  const { accessToken, refresh } = useAuth();
  const [state, setState] = React.useState<FormState>(() =>
    makeDefaultState(editing),
  );
  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  // Reset quando abre com outro registro ou fecha.
  React.useEffect(() => {
    if (open) {
      setState(makeDefaultState(editing));
      setSubmitError(null);
    }
  }, [open, editing]);

  const cronExpr = React.useMemo(() => {
    try {
      return builderToCron(state.builder);
    } catch {
      return "";
    }
  }, [state.builder]);

  const cronError = React.useMemo(() => {
    if (!cronExpr) return "Expressao cron invalida.";
    return validateCron(cronExpr);
  }, [cronExpr]);

  const nextRuns = React.useMemo(() => {
    if (cronError) return [];
    return computeNextRuns(cronExpr, state.timezone, 5);
  }, [cronExpr, cronError, state.timezone]);

  const patchBuilder = React.useCallback(
    (update: Partial<BuilderValue>) => {
      setState((prev) => ({
        ...prev,
        builder: { ...prev.builder, ...update } as BuilderValue,
      }));
    },
    [],
  );

  const setMode = React.useCallback((mode: BuilderMode) => {
    setState((prev) => {
      if (prev.builder.mode === mode) return prev;
      // Preserva hora/minuto entre os modos para uma UX menos abrupta.
      const hour =
        "hour" in prev.builder && typeof prev.builder.hour === "number"
          ? prev.builder.hour
          : 3;
      const minute =
        "minute" in prev.builder && typeof prev.builder.minute === "number"
          ? prev.builder.minute
          : 0;
      let next: BuilderValue;
      switch (mode) {
        case "daily":
          next = { mode: "daily", hour, minute };
          break;
        case "weekly":
          next = { mode: "weekly", dow: 1, hour, minute };
          break;
        case "monthly":
          next = { mode: "monthly", day: 1, hour, minute };
          break;
        case "custom":
          next = {
            mode: "custom",
            expr:
              prev.builder.mode === "custom"
                ? prev.builder.expr
                : (() => {
                    try {
                      return builderToCron(prev.builder);
                    } catch {
                      return "0 3 * * *";
                    }
                  })(),
          };
          break;
      }
      return { ...prev, builder: next };
    });
  }, []);

  const applyPreset = React.useCallback((preset: SchedulePreset) => {
    setState((prev) => ({
      ...prev,
      builder: cronToBuilder(preset.cron_expr),
    }));
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitError(null);
    if (cronError || !cronExpr) {
      setSubmitError(cronError ?? "Expressao cron invalida.");
      return;
    }
    let resolvedExpr: string;
    try {
      resolvedExpr = builderToCron(state.builder);
    } catch (err) {
      setSubmitError(
        err instanceof CronParseError
          ? err.message
          : "Expressao cron invalida.",
      );
      return;
    }
    setSubmitting(true);
    try {
      const companyIdPayload = state.companyId ? state.companyId : null;
      const saved = editing
        ? await updateSchedule(
            editing.id,
            {
              cron_expr: resolvedExpr,
              timezone: state.timezone,
              company_id: companyIdPayload,
              enabled: state.enabled,
            },
            {
              accessToken,
              onTokenRefreshed: () => {
                void refresh();
              },
            },
          )
        : await createSchedule(
            {
              cron_expr: resolvedExpr,
              timezone: state.timezone,
              company_id: companyIdPayload,
              enabled: state.enabled,
            },
            {
              accessToken,
              onTokenRefreshed: () => {
                void refresh();
              },
            },
          );
      onSaved(saved);
    } catch (err) {
      const detail = extractErrorDetail(err);
      if (err instanceof ApiError) {
        if (err.status === 400) {
          setSubmitError(
            detail ??
              "Dados invalidos. Verifique cron e timezone.",
          );
        } else if (err.status === 403) {
          setSubmitError(
            "Voce nao tem permissao para salvar agendamentos.",
          );
        } else if (err.status === 404) {
          setSubmitError("Agendamento nao encontrado.");
        } else {
          setSubmitError(
            detail ?? "Falha ao salvar. Tente novamente.",
          );
        }
      } else {
        setSubmitError("Erro de rede. Verifique a conexao e tente novamente.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={submitting ? () => undefined : onClose}
      title={editing ? "Editar agendamento" : "Novo agendamento"}
      description="Defina quando a coleta automatica deve rodar."
      dismissable={!submitting}
      maxWidth="max-w-xl"
    >
      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-4"
        noValidate
      >
        {/* Presets */}
        {presets.length > 0 ? (
          <div className="flex flex-col gap-2">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Sugestoes
            </span>
            <div className="flex flex-wrap gap-2">
              {presets.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => applyPreset(p)}
                  title={p.description}
                  className="inline-flex items-center rounded-md border border-border bg-muted/40 px-2.5 py-1 text-xs font-medium text-foreground transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {/* Empresa */}
        <div className="flex flex-col gap-1">
          <label
            htmlFor="schedule-company"
            className="text-sm font-medium"
          >
            Empresa
          </label>
          <select
            id="schedule-company"
            value={state.companyId}
            onChange={(e) =>
              setState((p) => ({ ...p, companyId: e.target.value }))
            }
            disabled={companiesLoading}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="">Todas as empresas (tenant-wide)</option>
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.razao_social}
              </option>
            ))}
          </select>
          <span className="text-xs text-muted-foreground">
            Deixe em branco para coletar de todas as empresas do tenant.
          </span>
        </div>

        {/* Modo */}
        <fieldset className="flex flex-col gap-2">
          <legend className="text-sm font-medium">Frequencia</legend>
          <div
            className="flex flex-wrap gap-2"
            role="radiogroup"
            aria-label="Frequencia"
          >
            {(
              [
                ["daily", "Diario"],
                ["weekly", "Semanal"],
                ["monthly", "Mensal"],
                ["custom", "Cron customizado"],
              ] as const
            ).map(([value, label]) => {
              const selected = state.builder.mode === value;
              return (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => setMode(value)}
                  className={`inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                    selected
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-background text-foreground hover:bg-accent"
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </fieldset>

        {/* Campos por modo */}
        <BuilderFields value={state.builder} onPatch={patchBuilder} />

        {/* Timezone */}
        <div className="flex flex-col gap-1">
          <label
            htmlFor="schedule-tz"
            className="text-sm font-medium"
          >
            Timezone
          </label>
          <select
            id="schedule-tz"
            value={state.timezone}
            onChange={(e) =>
              setState((p) => ({ ...p, timezone: e.target.value }))
            }
            className="h-9 rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {TZ_OPTIONS.map((tz) => (
              <option key={tz} value={tz}>
                {tz}
              </option>
            ))}
            {/* Permite TZ existente fora da lista (edicao). */}
            {editing &&
            !TZ_OPTIONS.includes(editing.timezone) &&
            editing.timezone === state.timezone ? (
              <option value={editing.timezone}>{editing.timezone}</option>
            ) : null}
          </select>
        </div>

        {/* Ativo/Pausado */}
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={state.enabled}
            onChange={(e) =>
              setState((p) => ({ ...p, enabled: e.target.checked }))
            }
          />
          <span>
            Ativar agora (se desmarcar, next_run_at fica vazio ate reativar)
          </span>
        </label>

        {/* Expressao e preview */}
        <div className="flex flex-col gap-2 rounded-md border border-border bg-muted/20 p-3">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <CalendarClock className="h-3.5 w-3.5" aria-hidden="true" />
            Expressao cron
          </div>
          <div className="font-mono text-sm" data-testid="cron-preview">
            {cronExpr || "—"}
          </div>
          {cronError ? (
            <p
              role="alert"
              className="text-xs text-destructive"
              data-testid="cron-error"
            >
              {cronError}
            </p>
          ) : (
            <div className="mt-1">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Proximos 5 runs ({state.timezone})
              </div>
              <ul
                className="mt-1 list-disc space-y-0.5 pl-5 text-sm tabular-nums"
                data-testid="next-runs"
              >
                {nextRuns.length === 0 ? (
                  <li className="text-muted-foreground">
                    Nenhum run nos proximos 2 anos.
                  </li>
                ) : (
                  nextRuns.map((d) => (
                    <li key={d.toISOString()}>
                      {formatRun(d, state.timezone)}
                    </li>
                  ))
                )}
              </ul>
            </div>
          )}
        </div>

        {submitError ? (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
          >
            <AlertTriangle
              className="mt-0.5 h-4 w-4 shrink-0"
              aria-hidden="true"
            />
            <span>{submitError}</span>
          </div>
        ) : null}

        <div className="flex items-center justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium text-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={submitting || cronError !== null}
            className="inline-flex h-9 items-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {submitting
              ? "Salvando..."
              : editing
                ? "Salvar alteracoes"
                : "Criar agendamento"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function BuilderFields({
  value,
  onPatch,
}: {
  value: BuilderValue;
  onPatch: (patch: Partial<BuilderValue>) => void;
}) {
  if (value.mode === "custom") {
    return (
      <div className="flex flex-col gap-1">
        <label
          htmlFor="schedule-cron-custom"
          className="text-sm font-medium"
        >
          Expressao cron (5 campos)
        </label>
        <input
          id="schedule-cron-custom"
          type="text"
          inputMode="text"
          spellCheck={false}
          autoComplete="off"
          value={value.expr}
          onChange={(e) => onPatch({ expr: e.target.value })}
          placeholder="ex: */15 * * * *"
          className="h-9 rounded-md border border-input bg-background px-3 font-mono text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <span className="text-xs text-muted-foreground">
          Formato Unix: <code>minuto hora dia mes dia-da-semana</code>. Use
          <code> * </code>para qualquer valor e <code>*/N</code> para step.
        </span>
      </div>
    );
  }

  const hour = "hour" in value ? value.hour : 3;
  const minute = "minute" in value ? value.minute : 0;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_auto_auto]">
      {value.mode === "weekly" ? (
        <div className="flex flex-col gap-1">
          <label
            htmlFor="schedule-dow"
            className="text-sm font-medium"
          >
            Dia da semana
          </label>
          <select
            id="schedule-dow"
            value={value.dow}
            onChange={(e) => onPatch({ dow: Number(e.target.value) })}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {Object.entries(DOW_LABEL_PT).map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      {value.mode === "monthly" ? (
        <div className="flex flex-col gap-1">
          <label
            htmlFor="schedule-day"
            className="text-sm font-medium"
          >
            Dia do mes
          </label>
          <select
            id="schedule-day"
            value={value.day}
            onChange={(e) => onPatch({ day: Number(e.target.value) })}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <span className="text-xs text-muted-foreground">
            Meses sem esse dia serao pulados (ex: dia 31 nao roda em
            fevereiro).
          </span>
        </div>
      ) : null}

      <div className="flex flex-col gap-1">
        <label
          htmlFor="schedule-hour"
          className="text-sm font-medium"
        >
          Hora
        </label>
        <select
          id="schedule-hour"
          value={hour}
          onChange={(e) => onPatch({ hour: Number(e.target.value) })}
          className="h-9 w-20 rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {Array.from({ length: 24 }, (_, i) => i).map((h) => (
            <option key={h} value={h}>
              {h.toString().padStart(2, "0")}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-1">
        <label
          htmlFor="schedule-minute"
          className="text-sm font-medium"
        >
          Minuto
        </label>
        <select
          id="schedule-minute"
          value={minute}
          onChange={(e) => onPatch({ minute: Number(e.target.value) })}
          className="h-9 w-20 rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {Array.from({ length: 60 }, (_, i) => i).map((m) => (
            <option key={m} value={m}>
              {m.toString().padStart(2, "0")}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
