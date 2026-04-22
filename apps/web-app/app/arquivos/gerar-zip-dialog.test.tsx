import * as React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

const useAuthMock = vi.fn();
vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => useAuthMock(),
}));

const createExportMock = vi.fn();
const getExportMock = vi.fn();

vi.mock("@/lib/api/exports", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/exports")>(
    "@/lib/api/exports",
  );
  return {
    ...actual,
    createExport: (...args: unknown[]) => createExportMock(...args),
    getExport: (...args: unknown[]) => getExportMock(...args),
  };
});

import { GerarZipDialog } from "./gerar-zip-dialog";

const companyFixture = {
  id: "cmp-1",
  tenant_id: "t-1",
  cnpj: "12345678901234",
  razao_social: "Empresa Teste",
  nome_fantasia: null,
  municipio_ibge: "3550308",
  uf: "SP",
  status: "active" as const,
  last_nsu: null,
  last_success_at: null,
  portal_provider: null,
  notes: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function makeExportRecord(overrides: Partial<Record<string, unknown>>) {
  return {
    id: "exp-1",
    tenant_id: "t-1",
    company_id: "cmp-1",
    requested_by_user_id: "u-1",
    kind: "zip_xml" as const,
    period_start: "2026-04-01",
    period_end: "2026-04-30",
    status: "queued" as const,
    file_id: null,
    items_count: 0,
    total_bytes: 0,
    error_code: null,
    error_message: null,
    started_at: null,
    finished_at: null,
    created_at: "2026-04-22T10:00:00Z",
    updated_at: "2026-04-22T10:00:00Z",
    download_url: null,
    expires_in: null,
    ...overrides,
  };
}

function withQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

beforeEach(() => {
  useAuthMock.mockReturnValue({
    accessToken: "tok",
    refresh: vi.fn(),
    user: { role: "operator", id: "u-1", email: "x@y.z", name: "X" },
  });
  createExportMock.mockReset();
  getExportMock.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("GerarZipDialog", () => {
  it("nao submete sem empresa selecionada", async () => {
    render(
      withQueryClient(
        <GerarZipDialog
          open
          onClose={() => undefined}
          companies={[companyFixture]}
        />,
      ),
    );
    // Confere que o select comeca vazio (estado inicial de "sem empresa").
    const select = screen.getByLabelText(/Empresa/i) as HTMLSelectElement;
    expect(select.value).toBe("");
    // Botao Gerar existe; ao clicar sem empresa, createExport nunca deve rodar.
    const submit = screen.getByRole("button", { name: /^Gerar$/i });
    fireEvent.click(submit);
    // Dar tempo para qualquer promessa/estado assincrono.
    await new Promise((r) => setTimeout(r, 50));
    expect(createExportMock).not.toHaveBeenCalled();
  });

  it("polling transiciona de running -> ready e exibe link de download", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    createExportMock.mockResolvedValue({
      export_id: "exp-1",
      status: "queued",
      job_id: "rq-1",
      enqueue_error: null,
    });
    getExportMock
      .mockResolvedValueOnce(makeExportRecord({ status: "running" }))
      .mockResolvedValueOnce(
        makeExportRecord({
          status: "ready",
          file_id: "file-1",
          download_url: "https://s3.example.com/signed",
          expires_in: 3600,
          items_count: 4,
        }),
      );

    render(
      withQueryClient(
        <GerarZipDialog
          open
          onClose={() => undefined}
          companies={[companyFixture]}
        />,
      ),
    );

    fireEvent.change(screen.getByLabelText(/Empresa/i), {
      target: { value: "cmp-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Gerar$/i }));

    await waitFor(() => {
      expect(createExportMock).toHaveBeenCalled();
    });

    await vi.advanceTimersByTimeAsync(3000);
    await waitFor(() => {
      expect(screen.getByTestId("export-polling")).toBeInTheDocument();
    });

    await vi.advanceTimersByTimeAsync(3000);
    await waitFor(() => {
      expect(screen.getByTestId("export-ready")).toBeInTheDocument();
    });
    const link = screen.getByRole("link", { name: /Baixar ZIP/i });
    expect(link.getAttribute("href")).toBe("https://s3.example.com/signed");
  });

  it("exibe painel de export vazio quando status=empty", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    createExportMock.mockResolvedValue({
      export_id: "exp-1",
      status: "queued",
      job_id: "rq-1",
      enqueue_error: null,
    });
    getExportMock.mockResolvedValue(makeExportRecord({ status: "empty" }));

    render(
      withQueryClient(
        <GerarZipDialog
          open
          onClose={() => undefined}
          companies={[companyFixture]}
        />,
      ),
    );
    fireEvent.change(screen.getByLabelText(/Empresa/i), {
      target: { value: "cmp-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Gerar$/i }));

    await waitFor(() => expect(createExportMock).toHaveBeenCalled());
    await vi.advanceTimersByTimeAsync(3000);

    await waitFor(() => {
      expect(screen.getByTestId("export-empty")).toBeInTheDocument();
    });
  });

  it("exibe erro quando createExport rejeita com queue_unavailable", async () => {
    const { ExportsApiError } = await vi.importActual<
      typeof import("@/lib/api/exports")
    >("@/lib/api/exports");
    createExportMock.mockRejectedValue(
      new ExportsApiError(502, "queue_unavailable", "Fila offline"),
    );

    render(
      withQueryClient(
        <GerarZipDialog
          open
          onClose={() => undefined}
          companies={[companyFixture]}
        />,
      ),
    );
    fireEvent.change(screen.getByLabelText(/Empresa/i), {
      target: { value: "cmp-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Gerar$/i }));

    await waitFor(() => {
      expect(screen.getByText(/Fila offline/i)).toBeInTheDocument();
    });
  });
});
