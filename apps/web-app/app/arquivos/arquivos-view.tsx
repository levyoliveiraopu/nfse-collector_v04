"use client";

import * as React from "react";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Download, FolderArchive } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { PeriodPicker, type PeriodRange } from "@/components/ui/period-picker";
import { listCompanies, type Company } from "@/lib/api/companies";
import {
  FILE_KIND_LABEL,
  FilesApiError,
  UI_FILTER_KINDS,
  formatBytes,
  getFileDownloadUrl,
  listFiles,
  type ApiFile,
  type FileKind,
} from "@/lib/api/files";

import { GerarZipDialog } from "./gerar-zip-dialog";
import { RetentionBanner } from "./retention-banner";

const WRITE_ROLES = new Set(["owner", "admin", "operator"]);
const PAGE_SIZE = 20;

export const FILES_QUERY_KEY = "files:list";
export const FILES_COMPANIES_QUERY_KEY = "files:companies";

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

/** Converte `PeriodRange` (YYYY-MM-DD) em ISO 8601 UTC com limites half-open. */
function periodToIso(range: PeriodRange): { from: string; to: string } {
  const [fy, fm, fd] = range.from.split("-").map(Number);
  const [ty, tm, td] = range.to.split("-").map(Number);
  const from = new Date(Date.UTC(fy, fm - 1, fd, 0, 0, 0, 0));
  // `to` exclusive: dia seguinte as 00:00 UTC.
  const to = new Date(Date.UTC(ty, tm - 1, td + 1, 0, 0, 0, 0));
  return { from: from.toISOString(), to: to.toISOString() };
}

export function ArquivosView() {
  const { accessToken, refresh, user } = useAuth();
  const role = user?.role ?? "viewer";
  const canGenerateZip = WRITE_ROLES.has(role);

  const [kind, setKind] = useState<"" | FileKind>("");
  const [companyId, setCompanyId] = useState<string>("");
  const [period, setPeriod] = useState<PeriodRange | null>(null);
  const [page, setPage] = useState(1);
  const [zipDialogOpen, setZipDialogOpen] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const ctx = useMemo(
    () => ({
      accessToken,
      onTokenRefreshed: () => {
        void refresh();
      },
    }),
    [accessToken, refresh],
  );

  // Reset para pagina 1 sempre que filtro muda.
  React.useEffect(() => {
    setPage(1);
  }, [kind, companyId, period]);

  const companiesQuery = useQuery({
    queryKey: [FILES_COMPANIES_QUERY_KEY],
    queryFn: () =>
      listCompanies(
        {
          pagination: { pageIndex: 0, pageSize: 100 },
          sort: null,
          filters: {},
        },
        ctx,
      ),
    enabled: Boolean(accessToken),
  });

  const companyById = useMemo(() => {
    const map = new Map<string, Company>();
    const rows = companiesQuery.data?.rows ?? [];
    for (const c of rows) map.set(c.id, c);
    return map;
  }, [companiesQuery.data]);

  const isoRange = useMemo(
    () => (period ? periodToIso(period) : null),
    [period],
  );

  const filesQuery = useQuery({
    queryKey: [
      FILES_QUERY_KEY,
      { kind, companyId, from: isoRange?.from, to: isoRange?.to, page },
    ],
    queryFn: () =>
      listFiles(
        {
          page,
          pageSize: PAGE_SIZE,
          kind: kind === "" ? undefined : kind,
          companyId: companyId || undefined,
          from: isoRange?.from,
          to: isoRange?.to,
        },
        ctx,
      ),
    enabled: Boolean(accessToken),
  });

  async function handleDownload(file: ApiFile) {
    setDownloadError(null);
    setDownloadingId(file.id);
    try {
      const { url } = await getFileDownloadUrl(file.id, ctx);
      if (typeof window !== "undefined") {
        window.open(url, "_blank", "noopener,noreferrer");
      }
    } catch (err) {
      setDownloadError(
        err instanceof FilesApiError
          ? err.message
          : "Falha ao gerar URL de download. Tente novamente.",
      );
    } finally {
      setDownloadingId(null);
    }
  }

  const items: ApiFile[] = filesQuery.data?.items ?? [];
  const total = filesQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const companies = companiesQuery.data?.rows ?? [];

  return (
    <div className="flex flex-col gap-4">
      <RetentionBanner />

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs">
            <span className="font-medium uppercase tracking-wide text-muted-foreground">
              Tipo
            </span>
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value as "" | FileKind)}
              className="h-9 rounded-md border border-input bg-background px-2 text-sm"
              aria-label="Filtrar por tipo de arquivo"
            >
              <option value="">Todos os tipos</option>
              {UI_FILTER_KINDS.map((k) => (
                <option key={k} value={k}>
                  {FILE_KIND_LABEL[k]}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-xs">
            <span className="font-medium uppercase tracking-wide text-muted-foreground">
              Empresa
            </span>
            <select
              value={companyId}
              onChange={(e) => setCompanyId(e.target.value)}
              disabled={companiesQuery.isLoading}
              className="h-9 rounded-md border border-input bg-background px-2 text-sm"
              aria-label="Filtrar por empresa"
            >
              <option value="">Todas as empresas</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.razao_social}
                </option>
              ))}
            </select>
          </label>

          <div className="flex flex-col gap-1 text-xs">
            <span className="font-medium uppercase tracking-wide text-muted-foreground">
              Periodo
            </span>
            <PeriodPicker
              value={period ?? undefined}
              onChange={(next) => setPeriod(next)}
            />
            {period ? (
              <button
                type="button"
                onClick={() => setPeriod(null)}
                className="self-start text-xs text-muted-foreground hover:text-foreground hover:underline"
              >
                Limpar periodo
              </button>
            ) : null}
          </div>
        </div>

        {canGenerateZip ? (
          <button
            type="button"
            onClick={() => setZipDialogOpen(true)}
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <FolderArchive className="h-4 w-4" aria-hidden="true" />
            Gerar arquivo
          </button>
        ) : null}
      </div>

      {downloadError ? (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
        >
          <AlertTriangle
            className="mt-0.5 h-4 w-4 shrink-0"
            aria-hidden="true"
          />
          <span>{downloadError}</span>
        </div>
      ) : null}

      <section
        aria-label="Arquivos do tenant"
        className="rounded-lg border border-border bg-card text-card-foreground shadow-sm"
      >
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          <span
            className="text-xs text-muted-foreground"
            data-testid="total-count"
          >
            {total} arquivo{total === 1 ? "" : "s"}
          </span>
        </header>

        {filesQuery.isLoading ? (
          <p className="px-4 py-6 text-sm text-muted-foreground" role="status">
            Carregando arquivos…
          </p>
        ) : filesQuery.isError ? (
          <div className="flex flex-col gap-2 px-4 py-6 text-sm" role="alert">
            <p className="text-destructive">
              {filesQuery.error instanceof FilesApiError
                ? filesQuery.error.message
                : "Nao foi possivel carregar os arquivos."}
            </p>
            <button
              type="button"
              onClick={() => filesQuery.refetch()}
              className="self-start rounded-md border border-border px-3 py-1 text-xs hover:bg-accent"
            >
              Tentar novamente
            </button>
          </div>
        ) : items.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted-foreground">
            Nenhum arquivo encontrado com os filtros atuais.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left">Tipo</th>
                  <th className="px-4 py-2 text-left">Empresa</th>
                  <th className="px-4 py-2 text-left">Arquivo</th>
                  <th className="px-4 py-2 text-right">Tamanho</th>
                  <th className="px-4 py-2 text-left">Criado em</th>
                  <th className="px-4 py-2" aria-label="Acoes" />
                </tr>
              </thead>
              <tbody>
                {items.map((file) => {
                  const resolvedCompany = companyId
                    ? companyById.get(companyId) ?? null
                    : null;
                  const companyLabel = resolvedCompany
                    ? resolvedCompany.razao_social
                    : file.source_execution_id
                      ? `Execucao ${file.source_execution_id.slice(0, 8)}…`
                      : "—";
                  const isDownloading = downloadingId === file.id;
                  const objectBasename =
                    file.object_key.split("/").pop() || file.object_key;
                  return (
                    <tr
                      key={file.id}
                      className="border-t border-border hover:bg-muted/30"
                      data-testid={`file-row-${file.id}`}
                    >
                      <td className="px-4 py-2">
                        {FILE_KIND_LABEL[file.kind]}
                      </td>
                      <td className="px-4 py-2 text-xs text-muted-foreground">
                        {companyLabel}
                      </td>
                      <td
                        className="px-4 py-2 font-mono text-xs"
                        title={file.object_key}
                      >
                        {objectBasename}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {formatBytes(file.bytes)}
                      </td>
                      <td className="px-4 py-2 text-xs">
                        {formatDate(file.created_at)}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <button
                          type="button"
                          onClick={() => handleDownload(file)}
                          disabled={isDownloading}
                          className="inline-flex h-8 items-center gap-1 rounded-md border border-border px-2 text-xs transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
                          aria-label={`Baixar ${objectBasename}`}
                        >
                          <Download className="h-3.5 w-3.5" aria-hidden="true" />
                          {isDownloading ? "Gerando…" : "Baixar"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 ? (
          <footer className="flex items-center justify-between border-t border-border px-4 py-2 text-xs">
            <span>
              Pagina {page} de {totalPages}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="rounded-md border border-border px-2 py-1 disabled:opacity-50"
              >
                Anterior
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-md border border-border px-2 py-1 disabled:opacity-50"
              >
                Proxima
              </button>
            </div>
          </footer>
        ) : null}
      </section>

      {canGenerateZip ? (
        <GerarZipDialog
          open={zipDialogOpen}
          onClose={() => setZipDialogOpen(false)}
          companies={companies}
          companiesLoading={companiesQuery.isLoading}
        />
      ) : null}
    </div>
  );
}
