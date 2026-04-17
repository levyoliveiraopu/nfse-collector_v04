import * as React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/execucoes/e1",
  useSearchParams: () => new URLSearchParams(""),
}));

const useAuthMock = vi.fn();
vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => useAuthMock(),
}));

const getExecutionMock = vi.fn();
const listExecutionItemsMock = vi.fn();
vi.mock("@/lib/api/executions", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/executions")>(
    "@/lib/api/executions",
  );
  return {
    ...actual,
    getExecution: (...a: unknown[]) =>
      (getExecutionMock as (...args: unknown[]) => unknown)(...a),
    listExecutionItems: (...a: unknown[]) =>
      (listExecutionItemsMock as (...args: unknown[]) => unknown)(...a),
  };
});

import { ExecucaoDetailView } from "./execucao-detail-view";

function withClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

afterEach(() => {
  vi.useRealTimers();
});

beforeEach(() => {
  useAuthMock.mockReset();
  getExecutionMock.mockReset();
  listExecutionItemsMock.mockReset();
  useAuthMock.mockReturnValue({
    accessToken: "tok",
    refresh: vi.fn(),
    user: { userId: "u-1", tenantId: "t-1", role: "operator" },
    status: "authenticated",
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
  });
});

function makeExecution(overrides: Record<string, unknown> = {}) {
  return {
    id: "e1",
    tenant_id: "t-1",
    company_id: "c1",
    trigger: "manual",
    status: "running",
    period_start: "2026-04-01",
    period_end: "2026-04-17",
    started_at: "2026-04-17T10:00:00Z",
    finished_at: null,
    nsu_from: 0,
    nsu_to: null,
    items_total: 10,
    items_ok: 3,
    items_fail: 1,
    error_summary: null,
    triggered_by_user_id: "u-1",
    created_at: "2026-04-17T10:00:00Z",
    updated_at: "2026-04-17T10:00:05Z",
    ...overrides,
  };
}

describe("ExecucaoDetailView — progresso + polling", () => {
  it("renderiza barra de progresso com valores corretos", async () => {
    getExecutionMock.mockResolvedValue(makeExecution());
    listExecutionItemsMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 50,
      total: 0,
    });

    render(withClient(<ExecucaoDetailView executionId="e1" />));
    const bar = await screen.findByRole("progressbar");
    expect(bar.getAttribute("aria-valuenow")).toBe("4");
    expect(bar.getAttribute("aria-valuemax")).toBe("10");
    expect(screen.getByText("40%")).toBeInTheDocument();
  });

  it("mostra indicador de polling enquanto status nao e terminal", async () => {
    getExecutionMock.mockResolvedValue(makeExecution({ status: "running" }));
    listExecutionItemsMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 50,
      total: 0,
    });
    render(withClient(<ExecucaoDetailView executionId="e1" />));
    expect(await screen.findByText(/Atualizando a cada 2s/i)).toBeInTheDocument();
  });

  it("nao mostra indicador de polling em status terminal (succeeded)", async () => {
    getExecutionMock.mockResolvedValue(makeExecution({ status: "succeeded" }));
    listExecutionItemsMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 50,
      total: 0,
    });
    render(withClient(<ExecucaoDetailView executionId="e1" />));
    await screen.findByRole("progressbar");
    expect(screen.queryByText(/Atualizando a cada 2s/i)).toBeNull();
  });

  it("refaz query detail quando status ainda nao e terminal (polling 2s)", async () => {
    getExecutionMock
      .mockResolvedValueOnce(makeExecution({ status: "running" }))
      .mockResolvedValue(
        makeExecution({
          status: "succeeded",
          items_total: 3,
          items_ok: 3,
          items_fail: 0,
        }),
      );
    listExecutionItemsMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 50,
      total: 0,
    });
    render(withClient(<ExecucaoDetailView executionId="e1" />));
    await screen.findByRole("progressbar");
    // Aguarda o refetchInterval (2s) disparar pelo menos uma vez.
    await waitFor(
      () => expect(getExecutionMock).toHaveBeenCalledTimes(2),
      { timeout: 4000 },
    );
  }, 10000);

  it("404 exibe mensagem clara", async () => {
    const { ExecutionsApiError } = await import("@/lib/api/executions");
    getExecutionMock.mockRejectedValue(
      new ExecutionsApiError(404, "not_found", "Recurso nao encontrado."),
    );
    render(withClient(<ExecucaoDetailView executionId="missing" />));
    expect(
      await screen.findByText(/nao encontrada/i),
    ).toBeInTheDocument();
  });
});

describe("ExecucaoDetailView — filtro de items", () => {
  it("muda status filter e refaz query", async () => {
    getExecutionMock.mockResolvedValue(makeExecution({ status: "succeeded" }));
    listExecutionItemsMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 50,
      total: 0,
    });

    render(withClient(<ExecucaoDetailView executionId="e1" />));
    await screen.findByRole("progressbar");

    const falhouTab = await screen.findByRole("tab", { name: /Falhou/i });
    fireEvent.click(falhouTab);
    await waitFor(() => {
      const calls = listExecutionItemsMock.mock.calls;
      expect(
        calls.some(
          (c) => (c as unknown[])[1] && ((c as unknown[])[1] as { status?: string }).status === "failed",
        ),
      ).toBe(true);
    });
  });
});

describe("ExecucaoDetailView — reprocessar", () => {
  it("botao Reprocessar fica aria-disabled ate APP-06/API-10", async () => {
    getExecutionMock.mockResolvedValue(makeExecution({ status: "succeeded" }));
    listExecutionItemsMock.mockResolvedValue({
      items: [
        {
          id: "i1",
          tenant_id: "t-1",
          execution_id: "e1",
          nsu: 1,
          chave_nfse: "x",
          cnpj_emitente: null,
          data_emissao: null,
          valor: null,
          xml_object_key: null,
          status: "failed",
          error_code: "PARSE_ERROR",
          error_message: null,
          created_at: "",
          updated_at: "",
        },
      ],
      page: 1,
      page_size: 50,
      total: 1,
    });

    render(withClient(<ExecucaoDetailView executionId="e1" />));
    await screen.findByRole("progressbar");

    const button = await screen.findByRole("button", {
      name: /Reprocessar selecionados/i,
    });
    expect(button.getAttribute("aria-disabled")).toBe("true");
    expect(button.getAttribute("title")).toMatch(/APP-06|API-10/);
  });
});
