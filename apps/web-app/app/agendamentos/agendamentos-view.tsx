"use client";

import * as React from "react";
import { useCallback, useMemo, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { AlertTriangle, Pencil, Plus, Trash2 } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError } from "@/lib/auth/api-client";
import {
  deleteSchedule,
  extractErrorDetail,
  listSchedulePresets,
  listSchedules,
  toggleSchedule,
  type Schedule,
  type SchedulePreset,
} from "@/lib/api/schedules";
import { listCompanies, type Company } from "@/lib/api/companies";
import { humanizeCron } from "@/lib/schedules/cron";

import { ScheduleFormDialog } from "./schedule-form-dialog";

const WRITE_ROLES = new Set(["owner", "admin", "operator"]);
const DELETE_ROLES = new Set(["owner", "admin"]);

export const SCHEDULES_QUERY_KEY = "schedules:list";
export const SCHEDULES_PRESETS_KEY = "schedules:presets";
export const SCHEDULES_COMPANIES_KEY = "schedules:companies";

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

export function AgendamentosView() {
  const { accessToken, refresh, user } = useAuth();
  const role = user?.role ?? "viewer";
  const canWrite = WRITE_ROLES.has(role);
  const canDelete = DELETE_ROLES.has(role);
  const queryClient = useQueryClient();

  const ctx = useMemo(
    () => ({
      accessToken,
      onTokenRefreshed: () => {
        void refresh();
      },
    }),
    [accessToken, refresh],
  );

  const schedulesQuery = useQuery({
    queryKey: [SCHEDULES_QUERY_KEY],
    queryFn: () => listSchedules({ page: 1, pageSize: 100 }, ctx),
  });

  const presetsQuery = useQuery({
    queryKey: [SCHEDULES_PRESETS_KEY],
    queryFn: () => listSchedulePresets(ctx),
  });

  // Companies para resolver o label "Empresa" por UUID. Tamanho grande
  // basta para os tenants tipicos (dezenas a centenas de CNPJs).
  const companiesQuery = useQuery({
    queryKey: [SCHEDULES_COMPANIES_KEY],
    queryFn: () =>
      listCompanies(
        {
          pagination: { pageIndex: 0, pageSize: 100 },
          sort: null,
          filters: {},
        },
        ctx,
      ),
  });

  const companyById = useMemo(() => {
    const map = new Map<string, Company>();
    const rows = companiesQuery.data?.rows ?? [];
    for (const c of rows) map.set(c.id, c);
    return map;
  }, [companiesQuery.data]);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [toggleErrorId, setToggleErrorId] = useState<string | null>(null);
  const [toggleErrorMsg, setToggleErrorMsg] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      toggleSchedule(id, enabled, ctx),
    onSuccess: () => {
      setToggleErrorId(null);
      setToggleErrorMsg(null);
      void queryClient.invalidateQueries({ queryKey: [SCHEDULES_QUERY_KEY] });
    },
    onError: (err, variables) => {
      setToggleErrorId(variables.id);
      setToggleErrorMsg(
        extractErrorDetail(err) ??
          (err instanceof ApiError && err.status === 403
            ? "Voce nao tem permissao para alterar este agendamento."
            : "Falha ao alterar o agendamento. Tente novamente."),
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSchedule(id, ctx),
    onSuccess: () => {
      setDeletingId(null);
      setDeleteError(null);
      void queryClient.invalidateQueries({ queryKey: [SCHEDULES_QUERY_KEY] });
    },
    onError: (err) => {
      setDeleteError(
        extractErrorDetail(err) ??
          (err instanceof ApiError && err.status === 403
            ? "Voce nao tem permissao para excluir agendamentos."
            : "Falha ao excluir. Tente novamente."),
      );
    },
  });

  const handleCreated = useCallback(() => {
    setDialogOpen(false);
    setEditing(null);
    void queryClient.invalidateQueries({ queryKey: [SCHEDULES_QUERY_KEY] });
  }, [queryClient]);

  const handleEdit = useCallback((schedule: Schedule) => {
    setEditing(schedule);
    setDialogOpen(true);
  }, []);

  const handleDelete = useCallback(
    (schedule: Schedule) => {
      if (!canDelete) return;
      if (
        typeof window !== "undefined" &&
        !window.confirm(
          `Excluir este agendamento? Esta acao nao pode ser desfeita.`,
        )
      ) {
        return;
      }
      setDeletingId(schedule.id);
      deleteMutation.mutate(schedule.id);
    },
    [canDelete, deleteMutation],
  );

  const handleToggle = useCallback(
    (schedule: Schedule) => {
      if (!canWrite) return;
      toggleMutation.mutate({ id: schedule.id, enabled: !schedule.enabled });
    },
    [canWrite, toggleMutation],
  );

  const presets: SchedulePreset[] = presetsQuery.data ?? [];
  const schedules: Schedule[] = schedulesQuery.data?.items ?? [];

  return (
    <>
      <div className="flex justify-end">
        {canWrite ? (
          <button
            type="button"
            onClick={() => {
              setEditing(null);
              setDialogOpen(true);
            }}
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Novo agendamento
          </button>
        ) : null}
      </div>

      {deleteError ? (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
        >
          <AlertTriangle
            className="mt-0.5 h-4 w-4 shrink-0"
            aria-hidden="true"
          />
          <span>{deleteError}</span>
        </div>
      ) : null}

      <div className="overflow-hidden rounded-md border border-border">
        <table className="w-full divide-y divide-border">
          <thead className="bg-muted/50">
            <tr className="text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <th className="px-3 py-2">Empresa</th>
              <th className="px-3 py-2">Quando</th>
              <th className="px-3 py-2">Timezone</th>
              <th className="px-3 py-2">Proximo run</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2 text-right">Acoes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border bg-background">
            {schedulesQuery.isLoading ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-3 py-6 text-center text-sm text-muted-foreground"
                >
                  Carregando agendamentos...
                </td>
              </tr>
            ) : schedulesQuery.isError ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-3 py-6 text-center text-sm text-destructive"
                >
                  Falha ao carregar agendamentos.
                </td>
              </tr>
            ) : schedules.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-3 py-6 text-center text-sm text-muted-foreground"
                >
                  Nenhum agendamento cadastrado. Clique em &quot;Novo
                  agendamento&quot; para comecar.
                </td>
              </tr>
            ) : (
              schedules.map((s) => {
                const company = s.company_id
                  ? companyById.get(s.company_id) ?? null
                  : null;
                const companyLabel = s.company_id
                  ? company?.razao_social ??
                    `Empresa ${s.company_id.slice(0, 8)}`
                  : "Todas as empresas";
                const isTogglingThis =
                  toggleMutation.isPending &&
                  toggleMutation.variables?.id === s.id;
                const isDeletingThis =
                  deleteMutation.isPending && deletingId === s.id;
                return (
                  <tr key={s.id} data-testid={`schedule-row-${s.id}`}>
                    <td className="px-3 py-2 text-sm">{companyLabel}</td>
                    <td className="px-3 py-2 text-sm">
                      <div className="flex flex-col">
                        <span>{humanizeCron(s.cron_expr)}</span>
                        <span className="font-mono text-xs text-muted-foreground">
                          {s.cron_expr}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-2 text-sm text-muted-foreground">
                      {s.timezone}
                    </td>
                    <td className="px-3 py-2 text-sm tabular-nums text-muted-foreground">
                      {formatDateTime(s.next_run_at)}
                    </td>
                    <td className="px-3 py-2 text-sm">
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          role="switch"
                          aria-checked={s.enabled}
                          aria-label={
                            s.enabled
                              ? "Pausar agendamento"
                              : "Ativar agendamento"
                          }
                          disabled={!canWrite || isTogglingThis}
                          onClick={() => handleToggle(s)}
                          className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60 ${
                            s.enabled
                              ? "bg-primary"
                              : "bg-muted-foreground/30"
                          }`}
                        >
                          <span
                            className={`inline-block h-4 w-4 transform rounded-full bg-background transition ${
                              s.enabled ? "translate-x-4" : "translate-x-0.5"
                            }`}
                          />
                        </button>
                        <StatusBadge
                          variant={s.enabled ? "success" : "pending"}
                          label={s.enabled ? "Ativo" : "Pausado"}
                          size="sm"
                        />
                      </div>
                      {toggleErrorId === s.id && toggleErrorMsg ? (
                        <p
                          role="alert"
                          className="mt-1 text-xs text-destructive"
                        >
                          {toggleErrorMsg}
                        </p>
                      ) : null}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <div className="inline-flex items-center gap-1">
                        {canWrite ? (
                          <button
                            type="button"
                            onClick={() => handleEdit(s)}
                            aria-label="Editar agendamento"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          >
                            <Pencil className="h-4 w-4" aria-hidden="true" />
                          </button>
                        ) : null}
                        {canDelete ? (
                          <button
                            type="button"
                            onClick={() => handleDelete(s)}
                            disabled={isDeletingThis}
                            aria-label="Excluir agendamento"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition hover:bg-destructive/10 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            <Trash2 className="h-4 w-4" aria-hidden="true" />
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {canWrite ? (
        <ScheduleFormDialog
          open={dialogOpen}
          onClose={() => {
            setDialogOpen(false);
            setEditing(null);
          }}
          onSaved={handleCreated}
          editing={editing}
          presets={presets}
          companies={companiesQuery.data?.rows ?? []}
          companiesLoading={companiesQuery.isLoading}
        />
      ) : null}
    </>
  );
}
