"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Pencil, Trash2 } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { Modal } from "@/components/ui/modal";
import { ApiError } from "@/lib/auth/api-client";
import {
  COMPANY_STATUS_LABEL,
  deleteCompany,
  formatCnpj,
  updateCompany,
  type Company,
  type CompanyStatus,
} from "@/lib/api/companies";

import { EMPRESAS_QUERY_KEY } from "../../empresas-table";

const WRITE_ROLES = new Set(["owner", "admin", "operator"]);
const DELETE_ROLES = new Set(["owner", "admin"]);

function formatDate(iso: string | null): string {
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

export function OverviewTab({ company }: { company: Company }) {
  const { user } = useAuth();
  const role = user?.role ?? "viewer";
  const canEdit = WRITE_ROLES.has(role);
  const canDelete = DELETE_ROLES.has(role);

  const [editOpen, setEditOpen] = React.useState(false);
  const [deleteOpen, setDeleteOpen] = React.useState(false);

  return (
    <div className="flex flex-col gap-6">
      <section
        aria-label="Dados cadastrais"
        className="rounded-lg border border-border bg-card text-card-foreground shadow-sm"
      >
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold">Dados cadastrais</h2>
          <div className="flex items-center gap-2">
            {canEdit ? (
              <button
                type="button"
                onClick={() => setEditOpen(true)}
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border bg-background px-3 text-xs font-medium transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                Editar
              </button>
            ) : null}
            {canDelete ? (
              <button
                type="button"
                onClick={() => setDeleteOpen(true)}
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-destructive/40 bg-background px-3 text-xs font-medium text-destructive transition hover:bg-destructive/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive"
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                Excluir
              </button>
            ) : null}
          </div>
        </header>
        <dl className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2">
          <Field label="CNPJ" value={formatCnpj(company.cnpj)} mono />
          <Field label="Razao social" value={company.razao_social} />
          <Field label="Nome fantasia" value={company.nome_fantasia ?? "—"} />
          <Field
            label="Municipio (IBGE)"
            value={`${company.municipio_ibge} (${company.uf})`}
          />
          <Field
            label="Status"
            value={COMPANY_STATUS_LABEL[company.status]}
          />
          <Field
            label="Provedor do portal"
            value={company.portal_provider ?? "—"}
          />
        </dl>
      </section>

      <section
        aria-label="Atividade"
        className="grid grid-cols-1 gap-4 sm:grid-cols-2"
      >
        <ActivityCard
          title="Ultima coleta com sucesso"
          value={formatDate(company.last_success_at)}
          hint={
            company.last_nsu !== null
              ? `Ultimo NSU registrado: ${company.last_nsu}`
              : "Sem NSU registrado ainda"
          }
        />
        <ActivityCard
          title="Proxima execucao agendada"
          value="Sem agendamento"
          hint="Agendamentos chegam em APP-08 / API-08."
        />
      </section>

      {editOpen ? (
        <EditCompanyDialog
          company={company}
          open={editOpen}
          onClose={() => setEditOpen(false)}
        />
      ) : null}
      {deleteOpen ? (
        <DeleteCompanyDialog
          company={company}
          open={deleteOpen}
          onClose={() => setDeleteOpen(false)}
        />
      ) : null}
    </div>
  );
}

function Field({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd
        className={
          mono
            ? "mt-1 font-mono text-sm tabular-nums"
            : "mt-1 text-sm"
        }
      >
        {value}
      </dd>
    </div>
  );
}

function ActivityCard({
  title,
  value,
  hint,
}: {
  title: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      <p className="mt-2 text-lg font-semibold tabular-nums">{value}</p>
      {hint ? (
        <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------
// Dialogs
// ---------------------------------------------------------------------

const EDITABLE_STATUSES: readonly CompanyStatus[] = [
  "active",
  "paused",
  "disabled",
];

function EditCompanyDialog({
  company,
  open,
  onClose,
}: {
  company: Company;
  open: boolean;
  onClose: () => void;
}) {
  const { accessToken, refresh } = useAuth();
  const queryClient = useQueryClient();

  const [razaoSocial, setRazaoSocial] = React.useState(company.razao_social);
  const [nomeFantasia, setNomeFantasia] = React.useState(
    company.nome_fantasia ?? "",
  );
  const [status, setStatus] = React.useState<CompanyStatus>(company.status);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await updateCompany(
        company.id,
        {
          razao_social: razaoSocial.trim(),
          nome_fantasia: nomeFantasia.trim() || null,
          status,
        },
        {
          accessToken,
          onTokenRefreshed: () => {
            void refresh();
          },
        },
      );
      await queryClient.invalidateQueries({
        queryKey: ["empresas:detail", company.id],
      });
      await queryClient.invalidateQueries({ queryKey: [EMPRESAS_QUERY_KEY] });
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError("Voce nao tem permissao para editar esta empresa.");
      } else if (err instanceof ApiError && err.status === 400) {
        setError("Payload invalido. Reveja os campos.");
      } else {
        setError("Nao foi possivel salvar. Tente novamente.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={submitting ? () => undefined : onClose}
      title="Editar empresa"
      description={`Alterando ${formatCnpj(company.cnpj)}. CNPJ e imutavel.`}
      maxWidth="max-w-lg"
      dismissable={!submitting}
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <div className="flex flex-col gap-1">
          <label htmlFor="edit-razao" className="text-sm font-medium">
            Razao social
          </label>
          <input
            id="edit-razao"
            value={razaoSocial}
            onChange={(e) => setRazaoSocial(e.target.value)}
            required
            minLength={2}
            maxLength={200}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="edit-fantasia" className="text-sm font-medium">
            Nome fantasia{" "}
            <span className="text-xs font-normal text-muted-foreground">
              (opcional)
            </span>
          </label>
          <input
            id="edit-fantasia"
            value={nomeFantasia}
            onChange={(e) => setNomeFantasia(e.target.value)}
            maxLength={200}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="edit-status" className="text-sm font-medium">
            Status
          </label>
          <select
            id="edit-status"
            value={status}
            onChange={(e) => setStatus(e.target.value as CompanyStatus)}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {EDITABLE_STATUSES.map((s) => (
              <option key={s} value={s}>
                {COMPANY_STATUS_LABEL[s]}
              </option>
            ))}
          </select>
        </div>
        {error ? (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        ) : null}
        <div className="flex items-center justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex h-9 items-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {submitting ? "Salvando..." : "Salvar alteracoes"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function DeleteCompanyDialog({
  company,
  open,
  onClose,
}: {
  company: Company;
  open: boolean;
  onClose: () => void;
}) {
  const { accessToken, refresh } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function onConfirm() {
    setSubmitting(true);
    setError(null);
    try {
      await deleteCompany(company.id, {
        accessToken,
        onTokenRefreshed: () => {
          void refresh();
        },
      });
      await queryClient.invalidateQueries({ queryKey: [EMPRESAS_QUERY_KEY] });
      router.replace("/empresas");
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError("Voce nao tem permissao para excluir esta empresa.");
      } else if (err instanceof ApiError && err.status === 404) {
        setError("Empresa ja foi removida.");
      } else {
        setError("Nao foi possivel excluir. Tente novamente.");
      }
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={submitting ? () => undefined : onClose}
      title="Excluir empresa"
      description="A empresa sera marcada como removida. Esta acao pode ser desfeita criando uma nova empresa com o mesmo CNPJ."
      maxWidth="max-w-md"
      dismissable={!submitting}
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm">
          Confirma excluir{" "}
          <span className="font-semibold">{company.razao_social}</span> (
          {formatCnpj(company.cnpj)})?
        </p>
        {error ? (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        ) : null}
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={submitting}
            className="inline-flex h-9 items-center rounded-md bg-destructive px-3 text-sm font-medium text-destructive-foreground shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive"
          >
            {submitting ? "Excluindo..." : "Excluir empresa"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
