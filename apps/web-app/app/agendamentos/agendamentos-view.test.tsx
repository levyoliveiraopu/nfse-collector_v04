import * as React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/agendamentos",
  useSearchParams: () => new URLSearchParams(""),
}));

const useAuthMock = vi.fn();
vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => useAuthMock(),
}));

const listSchedulesMock = vi.fn();
const listSchedulePresetsMock = vi.fn();
const toggleScheduleMock = vi.fn();
const deleteScheduleMock = vi.fn();

vi.mock("@/lib/api/schedules", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/schedules")>(
    "@/lib/api/schedules",
  );
  return {
    ...actual,
    listSchedules: (...args: unknown[]) => listSchedulesMock(...args),
    listSchedulePresets: (...args: unknown[]) =>
      listSchedulePresetsMock(...args),
    toggleSchedule: (...args: unknown[]) => toggleScheduleMock(...args),
    deleteSchedule: (...args: unknown[]) => deleteScheduleMock(...args),
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

import { AgendamentosView } from "./agendamentos-view";

function withQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

function mockAuth(role: string) {
  useAuthMock.mockReturnValue({
    accessToken: "tok",
    refresh: vi.fn(),
    user: { userId: "u-1", tenantId: "t-1", role },
    status: "authenticated",
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
  });
}

const fakeSchedule = {
  id: "00000000-0000-0000-0000-000000000001",
  tenant_id: "t-1",
  company_id: null,
  cron_expr: "0 3 * * *",
  timezone: "America/Sao_Paulo",
  enabled: true,
  last_run_at: null,
  next_run_at: "2026-04-20T06:00:00Z",
  created_by_user_id: null,
  created_at: "2026-04-13T10:00:00Z",
  updated_at: "2026-04-13T10:00:00Z",
};

beforeEach(() => {
  useAuthMock.mockReset();
  listSchedulesMock.mockReset();
  listSchedulePresetsMock.mockReset();
  toggleScheduleMock.mockReset();
  deleteScheduleMock.mockReset();
  listCompaniesMock.mockReset();

  listSchedulesMock.mockResolvedValue({
    items: [fakeSchedule],
    page: 1,
    page_size: 100,
    total: 1,
  });
  listSchedulePresetsMock.mockResolvedValue([]);
  listCompaniesMock.mockResolvedValue({ rows: [], total: 0 });
});

describe("AgendamentosView", () => {
  it("oculta botao 'Novo agendamento' para viewer", async () => {
    mockAuth("viewer");
    render(withQueryClient(<AgendamentosView />));
    await waitFor(() =>
      expect(listSchedulesMock).toHaveBeenCalled(),
    );
    expect(
      screen.queryByRole("button", { name: /novo agendamento/i }),
    ).toBeNull();
  });

  it("mostra botao 'Novo agendamento' para owner/admin/operator", async () => {
    for (const role of ["owner", "admin", "operator"]) {
      mockAuth(role);
      const { unmount } = render(withQueryClient(<AgendamentosView />));
      expect(
        await screen.findByRole("button", { name: /novo agendamento/i }),
      ).toBeInTheDocument();
      unmount();
    }
  });

  it("renderiza linha de agendamento com cron humanizado e status Ativo", async () => {
    mockAuth("admin");
    render(withQueryClient(<AgendamentosView />));
    expect(
      await screen.findByText(/Todo dia as 03:00/),
    ).toBeInTheDocument();
    expect(screen.getByText(/0 3 \* \* \*/)).toBeInTheDocument();
    expect(screen.getByText(/Ativo/)).toBeInTheDocument();
    expect(
      screen.getByRole("switch", { name: /pausar agendamento/i }),
    ).toHaveAttribute("aria-checked", "true");
  });

  it("viewer ve toggle desabilitado (aria-checked verdadeiro mas disabled)", async () => {
    mockAuth("viewer");
    render(withQueryClient(<AgendamentosView />));
    const toggle = await screen.findByRole("switch", {
      name: /pausar agendamento/i,
    });
    expect(toggle).toBeDisabled();
  });

  it("toggle chama toggleSchedule com enabled=false ao clicar em agenda ativa", async () => {
    mockAuth("admin");
    toggleScheduleMock.mockResolvedValueOnce({
      ...fakeSchedule,
      enabled: false,
      next_run_at: null,
    });
    const { container } = render(withQueryClient(<AgendamentosView />));
    const toggle = await screen.findByRole("switch", {
      name: /pausar agendamento/i,
    });
    // Workaround: fireEvent via click nativo (sem user-event dep).
    toggle.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await waitFor(() =>
      expect(toggleScheduleMock).toHaveBeenCalledWith(
        fakeSchedule.id,
        false,
        expect.anything(),
      ),
    );
    // Garante que o componente ainda esta montado.
    expect(container.querySelector("table")).not.toBeNull();
  });

  it("owner ve botao de excluir; viewer nao ve", async () => {
    mockAuth("owner");
    const { unmount } = render(withQueryClient(<AgendamentosView />));
    expect(
      await screen.findByRole("button", { name: /excluir agendamento/i }),
    ).toBeInTheDocument();
    unmount();

    mockAuth("viewer");
    render(withQueryClient(<AgendamentosView />));
    await waitFor(() => expect(listSchedulesMock).toHaveBeenCalled());
    expect(
      screen.queryByRole("button", { name: /excluir agendamento/i }),
    ).toBeNull();
  });

  it("exibe fallback quando lista vem vazia", async () => {
    mockAuth("admin");
    listSchedulesMock.mockResolvedValueOnce({
      items: [],
      page: 1,
      page_size: 100,
      total: 0,
    });
    render(withQueryClient(<AgendamentosView />));
    expect(
      await screen.findByText(/Nenhum agendamento cadastrado/i),
    ).toBeInTheDocument();
  });
});
