"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AlertTriangle, Play } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { PeriodPicker } from "@/components/ui/period-picker";
import type { PeriodRange } from "@/lib/date/period";
import { computePresetRange } from "@/lib/date/period";
import { formatCnpj, listCompanies, type Company } from "@/lib/api/companies";
import {
  ExecutionsApiError,
  createExecutions,
  type CreatedExecution,
} from "@/lib/api/executions";

const WRITE_ROLES = new Set(["owner", "admin", "operator"]);

interface CompanyLoadState {
  status: "idle" | "loading" | "ready" | "error";
  items: Company[];
  error: string | null;
}

function useCompanies(): CompanyLoadState & { reload: () => void } {
  const { accessToken, refresh } = useAuth();
  const [state, setState] = React.useState<CompanyLoadState>({
    status: "idle",
    items: [],
    error: null,
  });

  const load = React.useCallback(async () => {
    if (!accessToken) return;
    setState({ status: "loading", items: [], error: null });
    try {
      const res = await listCompanies(
        {
          pagination: { pageIndex: 0, pageSize: 100 },
          sort: null,
          filters: { status: "active" },
        },
        {
          accessToken,
          onTokenRefreshed: () => {
            void refresh();
          },
        },
      );
      setState({ status: "ready", items: res.rows, error: null });
    } catch (err) {
      setState({
        status: "error",
        items: [],
        error:
          err instanceof Error
            ? err.message
            : "Nao foi possivel carregar empresas.",
      });
    }
  }, [accessToken, refresh]);

  React.useEffect(() => {
    void load();
  }, [load]);

  return { ...state, reload: () => void load() };
}

interface SubmitError {
  message: string;
  blockedCompanyIds: string[];
}

export function NovaExecucaoForm() {
  const router = useRouter();
  const { user, accessToken, refresh } = useAuth();
  const role = user?.role ?? "viewer";
  const canSubmit = WRITE_ROLES.has(role);

  const companies = useCompanies();
  const [selectedIds, setSelectedIds] = React.useState<string[]>([]);
  const [period, setPeriod] = React.useState<PeriodRange>(() =>
    computePresetRange("last_30d"),
  );
  const [dryRun, setDryRun] = React.useState(false);
  const [incremental, setIncremental] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<SubmitError | null>(null);

  const toggleCompany = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
    setSubmitError(null);
  };

  const selectAll = () => {
    setSelectedIds(companies.items.map((c) => c.id));
    setSubmitError(null);
  };
  const clearAll = () => {
    setSelectedIds([]);
    setSubmitError(null);
  };

  const disabled = !canSubmit || submitting || selectedIds.length === 0;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit || selectedIds.length === 0) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await createExecutions(
        {
          company_ids: selectedIds,
          period_start: period.from,
          period_end: period.to,
          dry_run: dryRun,
          trigger: "manual",
        },
        {
          accessToken,
          onTokenRefreshed: () => {
            void refresh();
          },
        },
      );
      const created: CreatedExecution[] = res.created;
      if (created.length === 1) {
        router.push(`/execucoes/${created[0].execution_id}`);
      } else {
        router.push(`/execucoes`);
      }
    } catch (err) {
      if (err instanceof ExecutionsApiError) {
        let message = err.message;
        if (err.code === "credential_missing_or_expired") {
          const missingCnpjs = err.extra.companyIds
            .map((id) => companies.items.find((c) => c.id === id))
            .filter((c): c is Company => Boolean(c))
            .map((c) => formatCnpj(c.cnpj));
          message =
            missingCnpjs.length > 0
              ? `Empresas sem credencial valida: ${missingCnpjs.join(", ")}. ` +
                "Acesse a aba Credencial de cada empresa para regularizar."
              : err.message;
        }
        if (err.code === "companies_not_found") {
          message =
            "Uma ou mais empresas selecionadas foram removidas. Atualize a lista e tente novamente.";
        }
        setSubmitError({ message, blockedCompanyIds: err.extra.companyIds });
      } else {
        setSubmitError({
          message: "Falha ao iniciar execucao. Tente novamente.",
          blockedCompanyIds: [],
        });
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (!canSubmit) {
    return (
      <div
        role="alert"
        className="flex items-start gap-2 rounded-md border border-border bg-card p-4 text-sm"
      >
        <AlertTriangle
          className="mt-0.5 h-4 w-4 text-warning"
          aria-hidden="true"
        />
        <div>
          <p className="font-medium">Sem permissao para criar execucoes</p>
          <p className="text-muted-foreground">
            Apenas owner, admin e operator podem disparar coletas. Seu papel
            atual e <strong>{role}</strong>.
          </p>
        </div>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-6 rounded-lg border border-border bg-card p-6 shadow-sm"
      aria-busy={submitting}
    >
      <fieldset className="flex flex-col gap-3">
        <legend className="text-sm font-semibold">Empresas</legend>
        {companies.status === "loading" ? (
          <p className="text-sm text-muted-foreground" role="status">
            Carregando empresas…
          </p>
        ) : companies.status === "error" ? (
          <div className="flex flex-col gap-2" role="alert">
            <p className="text-sm text-destructive">{companies.error}</p>
            <button
              type="button"
              onClick={companies.reload}
              className="self-start rounded-md border border-border px-3 py-1 text-xs hover:bg-accent"
            >
              Tentar novamente
            </button>
          </div>
        ) : companies.items.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhuma empresa ativa cadastrada.{" "}
            <Link href="/empresas" className="text-primary underline">
              Cadastrar uma
            </Link>
            .
          </p>
        ) : (
          <>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span>
                {selectedIds.length} de {companies.items.length} selecionadas
              </span>
              <button
                type="button"
                onClick={selectAll}
                className="text-primary hover:underline"
              >
                Selecionar todas
              </button>
              <button
                type="button"
                onClick={clearAll}
                className="text-primary hover:underline"
                disabled={selectedIds.length === 0}
              >
                Limpar
              </button>
            </div>
            <ul
              className="max-h-64 overflow-y-auto rounded-md border border-border"
              role="listbox"
              aria-multiselectable="true"
              aria-label="Empresas disponiveis"
            >
              {companies.items.map((c) => {
                const selected = selectedIds.includes(c.id);
                const blocked = submitError?.blockedCompanyIds.includes(c.id);
                return (
                  <li key={c.id} role="option" aria-selected={selected}>
                    <label
                      className={
                        "flex cursor-pointer items-center gap-3 border-b border-border px-3 py-2 text-sm last:border-b-0 hover:bg-accent " +
                        (blocked ? "bg-destructive/5" : "")
                      }
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggleCompany(c.id)}
                        className="h-4 w-4"
                        aria-label={`Selecionar ${c.razao_social}`}
                      />
                      <span className="flex min-w-0 flex-1 flex-col">
                        <span className="truncate font-medium">
                          {c.razao_social}
                        </span>
                        <span className="truncate font-mono text-xs text-muted-foreground">
                          {formatCnpj(c.cnpj)} · {c.uf}
                        </span>
                      </span>
                      {blocked ? (
                        <span className="text-xs text-destructive">
                          credencial
                        </span>
                      ) : null}
                    </label>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </fieldset>

      <fieldset className="flex flex-col gap-2">
        <legend className="text-sm font-semibold">Periodo</legend>
        <PeriodPicker value={period} onChange={setPeriod} />
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={incremental}
            onChange={(e) => setIncremental(e.target.checked)}
            className="h-4 w-4"
          />
          <span>
            Incremental desde o ultimo NSU
            <span className="ml-1 text-xs">
              (o worker ja respeita o <code>last_nsu</code> automaticamente — o
              periodo define apenas a janela)
            </span>
          </span>
        </label>
      </fieldset>

      <fieldset className="flex flex-col gap-2">
        <legend className="text-sm font-semibold">Opcoes</legend>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
            className="h-4 w-4"
          />
          <span>
            Dry-run
            <span className="ml-1 text-xs text-muted-foreground">
              (simula a coleta sem persistir items nem enviar XMLs ao storage)
            </span>
          </span>
        </label>
      </fieldset>

      {submitError ? (
        <div
          role="alert"
          className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
        >
          {submitError.message}
        </div>
      ) : null}

      <div className="flex items-center justify-end gap-2">
        <Link
          href="/execucoes"
          className="rounded-md border border-border px-3 py-2 text-sm hover:bg-accent"
        >
          Cancelar
        </Link>
        <button
          type="submit"
          disabled={disabled}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Play className="h-4 w-4" aria-hidden="true" />
          {submitting ? "Enfileirando…" : "Iniciar"}
        </button>
      </div>
    </form>
  );
}
