import * as React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/arquivos",
  useSearchParams: () => new URLSearchParams(""),
}));

const useAuthMock = vi.fn();
vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => useAuthMock(),
}));

const listFilesMock = vi.fn();
const getFileDownloadUrlMock = vi.fn();

vi.mock("@/lib/api/files", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/files")>(
    "@/lib/api/files",
  );
  return {
    ...actual,
    listFiles: (...args: unknown[]) => listFilesMock(...args),
    getFileDownloadUrl: (...args: unknown[]) => getFileDownloadUrlMock(...args),
  };
});

const listCompaniesMock = vi.fn();
vi.mock("@/lib/api/companies", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/companies")>(
    "@/lib/api/companies",
  );
  return {
    ...actual,
    listCompanies: (...args: unknown[]) => listCompaniesMock(...args),
  };
});

import { ArquivosView } from "./arquivos-view";

function withQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

function mockAuth(role: string = "operator") {
  useAuthMock.mockReturnValue({
    accessToken: "tok",
    refresh: vi.fn(),
    user: { role, id: "u-1", email: "x@y.z", name: "X" },
  });
}

const fileFixture = {
  id: "file-1",
  tenant_id: "t-1",
  kind: "nfse_xml" as const,
  object_key: "tenants/t-1/executions/exec-1/nfse/1.xml",
  bytes: 2048,
  checksum_sha256: "abc",
  source_execution_id: "exec-1",
  expires_at: null,
  created_at: "2026-04-22T09:00:00Z",
  updated_at: "2026-04-22T09:00:00Z",
};

beforeEach(() => {
  useAuthMock.mockReset();
  listFilesMock.mockReset();
  getFileDownloadUrlMock.mockReset();
  listCompaniesMock.mockReset();
  listCompaniesMock.mockResolvedValue({
    rows: [
      {
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
      },
    ],
    total: 1,
  });
});

describe("ArquivosView", () => {
  it("exibe banner de retencao SEMPRE (ADR-003)", async () => {
    mockAuth();
    listFilesMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 20,
      total: 0,
    });
    render(withQueryClient(<ArquivosView />));
    await waitFor(() => {
      expect(screen.getByTestId("retention-banner")).toBeInTheDocument();
    });
    expect(screen.getByText(/Retencao de 90 dias/i)).toBeInTheDocument();
  });

  it("renderiza mensagem de vazio quando nao ha arquivos", async () => {
    mockAuth();
    listFilesMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 20,
      total: 0,
    });
    render(withQueryClient(<ArquivosView />));
    await waitFor(() => {
      expect(
        screen.getByText(/Nenhum arquivo encontrado/i),
      ).toBeInTheDocument();
    });
  });

  it("lista arquivos e exibe contador total", async () => {
    mockAuth();
    listFilesMock.mockResolvedValue({
      items: [fileFixture],
      page: 1,
      page_size: 20,
      total: 1,
    });
    render(withQueryClient(<ArquivosView />));
    await waitFor(() => {
      expect(screen.getByTestId("file-row-file-1")).toBeInTheDocument();
    });
    expect(screen.getByTestId("total-count").textContent).toMatch(/1/);
  });

  it("clicar em Baixar chama getFileDownloadUrl e abre a URL", async () => {
    mockAuth();
    listFilesMock.mockResolvedValue({
      items: [fileFixture],
      page: 1,
      page_size: 20,
      total: 1,
    });
    getFileDownloadUrlMock.mockResolvedValue({
      url: "https://s3.example.com/signed",
      expires_in: 3600,
      expires_at: "2026-04-22T11:00:00Z",
    });
    const openSpy = vi
      .spyOn(window, "open")
      .mockImplementation(() => null as unknown as Window);

    render(withQueryClient(<ArquivosView />));

    const button = await screen.findByRole("button", { name: /Baixar/i });
    fireEvent.click(button);

    await waitFor(() => {
      expect(getFileDownloadUrlMock).toHaveBeenCalledWith(
        "file-1",
        expect.any(Object),
      );
    });
    await waitFor(() => {
      expect(openSpy).toHaveBeenCalledWith(
        "https://s3.example.com/signed",
        "_blank",
        "noopener,noreferrer",
      );
    });
    openSpy.mockRestore();
  });

  it("troca do filtro kind dispara nova query com kind na chave", async () => {
    mockAuth();
    listFilesMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 20,
      total: 0,
    });
    render(withQueryClient(<ArquivosView />));
    await waitFor(() => {
      expect(listFilesMock).toHaveBeenCalled();
    });
    const select = screen.getByLabelText(
      "Filtrar por tipo de arquivo",
    ) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "export" } });
    await waitFor(() => {
      const lastCall = listFilesMock.mock.calls.at(-1)!;
      expect(lastCall[0]).toMatchObject({ kind: "export" });
    });
  });

  it("oculta botao Gerar arquivo para viewer", async () => {
    mockAuth("viewer");
    listFilesMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 20,
      total: 0,
    });
    render(withQueryClient(<ArquivosView />));
    await waitFor(() => {
      expect(screen.getByTestId("retention-banner")).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("button", { name: /Gerar arquivo/i }),
    ).not.toBeInTheDocument();
  });
});
