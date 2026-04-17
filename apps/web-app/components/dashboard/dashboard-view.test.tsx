import * as React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(""),
}));

const useAuthMock = vi.fn();
vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => useAuthMock(),
}));

const listExecutionsMock = vi.fn();
vi.mock("@/lib/api/executions", async () => {
  const actual = await vi.importActual<
    typeof import("@/lib/api/executions")
  >("@/lib/api/executions");
  return {
    ...actual,
    listExecutions: (...args: Parameters<typeof actual.listExecutions>) =>
      listExecutionsMock(...args),
  };
});

const listOccurrencesMock = vi.fn();
vi.mock("@/lib/api/occurrences", async () => {
  const actual = await vi.importActual<
    typeof import("@/lib/api/occurrences")
  >("@/lib/api/occurrences");
  return {
    ...actual,
    listOccurrences: (...args: Parameters<typeof actual.listOccurrences>) =>
      listOccurrencesMock(...args),
  };
});

import { DashboardView } from "./dashboard-view";

function withQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

function seedAuth() {
  useAuthMock.mockReturnValue({
    accessToken: "tok",
    refresh: vi.fn(),
    user: { userId: "u-1", tenantId: "t-1", role: "owner" },
    status: "authenticated",
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
  });
}

function execListPayload({
  items = [],
  total = 0,
}: {
  items?: Array<Partial<
    import("@/lib/api/executions").Execution
  >>;
  total?: number;
} = {}) {
  return {
    items: items.map((it, idx) => ({
      id: String(idx + 1),
      tenant_id: "t-1",
      company_id: "c-1",
      trigger: "manual" as const,
      status: "succeeded" as const,
      period_start: "2026-04-01",
      period_end: "2026-04-15",
      started_at: "2026-04-15T12:00:00Z",
      finished_at: "2026-04-15T12:05:00Z",
      nsu_from: null,
      nsu_to: null,
      items_total: 10,
      items_ok: 10,
      items_fail: 0,
      error_summary: null,
      triggered_by_user_id: null,
      created_at: "2026-04-15T12:00:00Z",
      updated_at: "2026-04-15T12:05:00Z",
      ...it,
    })),
    page: 1,
    page_size: 100,
    total: total || items.length,
  };
}

beforeEach(() => {
  useAuthMock.mockReset();
  listExecutionsMock.mockReset();
  listOccurrencesMock.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("DashboardView (APP-02)", () => {
  it("renderiza 4 KPIStatCards, filtro de periodo e atalhos", () => {
    seedAuth();
    listExecutionsMock.mockResolvedValue(execListPayload());
    listOccurrencesMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 1,
      total: 0,
    });

    render(withQueryClient(<DashboardView />));

    expect(
      screen.getByRole("region", { name: /indicadores principais/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("article", { name: /notas coletadas/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("article", { name: /execucoes ok \/ total/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("article", { name: /ocorrencias abertas/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("article", { name: /certificados a vencer/i }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("group", { name: /presets de periodo/i }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("link", { name: /nova execucao/i }),
    ).toHaveAttribute("href", "/execucoes/nova");
    expect(
      screen.getByRole("link", { name: /ver ocorrencias/i }),
    ).toHaveAttribute("href", "/ocorrencias");
  });

  it("renderiza ate 10 itens na timeline com link para /execucoes/[id]", async () => {
    seedAuth();
    const items = Array.from({ length: 10 }, (_, i) => ({
      id: `exec-${i + 1}`,
      status: "succeeded" as const,
      items_total: 5,
      items_ok: 5,
    }));
    listExecutionsMock.mockResolvedValue(execListPayload({ items, total: 10 }));
    listOccurrencesMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 1,
      total: 0,
    });

    render(withQueryClient(<DashboardView />));

    const list = await screen.findByTestId("recent-timeline");
    const lis = list.querySelectorAll("li");
    expect(lis.length).toBe(10);

    const firstLink = list.querySelector("a") as HTMLAnchorElement | null;
    expect(firstLink?.getAttribute("href")).toBe("/execucoes/exec-1");
  });

  it("mostra estado vazio na timeline quando nao ha execucoes", async () => {
    seedAuth();
    listExecutionsMock.mockResolvedValue(execListPayload({ items: [], total: 0 }));
    listOccurrencesMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 1,
      total: 0,
    });

    render(withQueryClient(<DashboardView />));

    await waitFor(() =>
      expect(
        screen.getByText(/nenhuma execucao registrada no periodo/i),
      ).toBeInTheDocument(),
    );
  });

  it("exibe KPI 'Ocorrencias abertas' com o total do envelope", async () => {
    seedAuth();
    listExecutionsMock.mockResolvedValue(execListPayload());
    listOccurrencesMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 1,
      total: 7,
    });

    render(withQueryClient(<DashboardView />));

    const card = await screen.findByRole("article", {
      name: /ocorrencias abertas/i,
    });
    await waitFor(() => expect(card).toHaveTextContent("7"));
  });

  it("KPI 'Certificados a vencer' permanece em estado vazio (follow-up)", () => {
    seedAuth();
    listExecutionsMock.mockResolvedValue(execListPayload());
    listOccurrencesMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 1,
      total: 0,
    });

    render(withQueryClient(<DashboardView />));

    const card = screen.getByRole("article", {
      name: /certificados a vencer/i,
    });
    expect(card).toHaveAttribute("data-state", "empty");
  });
});
