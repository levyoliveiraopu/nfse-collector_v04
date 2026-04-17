import * as React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/agendamentos",
  useSearchParams: () => new URLSearchParams(""),
}));

const useAuthMock = vi.fn(() => ({
  accessToken: "tok",
  refresh: vi.fn(),
  user: { userId: "u-1", tenantId: "t-1", role: "admin" },
  status: "authenticated",
  login: vi.fn(),
  signup: vi.fn(),
  logout: vi.fn(),
}));
vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => useAuthMock(),
}));

const createScheduleMock = vi.fn();
const updateScheduleMock = vi.fn();
vi.mock("@/lib/api/schedules", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/schedules")>(
    "@/lib/api/schedules",
  );
  return {
    ...actual,
    createSchedule: (...args: unknown[]) => createScheduleMock(...args),
    updateSchedule: (...args: unknown[]) => updateScheduleMock(...args),
  };
});

import { ScheduleFormDialog } from "./schedule-form-dialog";
import { ApiError } from "@/lib/auth/api-client";

beforeEach(() => {
  createScheduleMock.mockReset();
  updateScheduleMock.mockReset();
});

const defaultProps = {
  onClose: vi.fn(),
  onSaved: vi.fn(),
  editing: null,
  presets: [
    {
      id: "daily_03",
      label: "Diario as 03:00",
      cron_expr: "0 3 * * *",
      description: "Todo dia 03:00",
    },
  ],
  companies: [
    {
      id: "c-1",
      tenant_id: "t-1",
      cnpj: "12345678000199",
      razao_social: "ACME LTDA",
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
  companiesLoading: false,
};

describe("ScheduleFormDialog", () => {
  it("mostra expressao cron default e proximos 5 runs", async () => {
    render(<ScheduleFormDialog {...defaultProps} open onSaved={vi.fn()} />);
    expect(screen.getByTestId("cron-preview")).toHaveTextContent("0 3 * * *");
    const runs = await screen.findByTestId("next-runs");
    // 5 bullet points com proximos disparos.
    expect(runs.querySelectorAll("li").length).toBe(5);
    expect(screen.queryByTestId("cron-error")).toBeNull();
  });

  it("permite aplicar preset e atualiza cron preview", () => {
    render(<ScheduleFormDialog {...defaultProps} open onSaved={vi.fn()} />);
    fireEvent.click(
      screen.getByRole("button", { name: /Diario as 03:00/i }),
    );
    expect(screen.getByTestId("cron-preview")).toHaveTextContent("0 3 * * *");
  });

  it("no modo customizado, cron invalido mostra erro e bloqueia submit", async () => {
    render(<ScheduleFormDialog {...defaultProps} open onSaved={vi.fn()} />);
    fireEvent.click(
      screen.getByRole("radio", { name: /Cron customizado/i }),
    );
    const input = await screen.findByLabelText(/Expressao cron/i);
    fireEvent.change(input, { target: { value: "lixo" } });
    expect(await screen.findByTestId("cron-error")).toBeInTheDocument();
    const submit = screen.getByRole("button", {
      name: /Criar agendamento/i,
    });
    expect(submit).toBeDisabled();
  });

  it("submit feliz chama createSchedule e onSaved", async () => {
    const savedSchedule = {
      id: "s-1",
      tenant_id: "t-1",
      company_id: null,
      cron_expr: "0 3 * * *",
      timezone: "America/Sao_Paulo",
      enabled: true,
      last_run_at: null,
      next_run_at: "2026-04-18T06:00:00Z",
      created_by_user_id: null,
      created_at: "2026-04-13T10:00:00Z",
      updated_at: "2026-04-13T10:00:00Z",
    };
    createScheduleMock.mockResolvedValueOnce(savedSchedule);
    const onSaved = vi.fn();
    render(
      <ScheduleFormDialog {...defaultProps} open onSaved={onSaved} />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /Criar agendamento/i }),
    );
    await waitFor(() =>
      expect(createScheduleMock).toHaveBeenCalledWith(
        {
          cron_expr: "0 3 * * *",
          timezone: "America/Sao_Paulo",
          company_id: null,
          enabled: true,
        },
        expect.anything(),
      ),
    );
    expect(onSaved).toHaveBeenCalledWith(savedSchedule);
  });

  it("400 do backend aparece como mensagem em alert", async () => {
    createScheduleMock.mockRejectedValueOnce(
      new ApiError(400, { detail: "cron_expr invalida: XYZ" }),
    );
    render(<ScheduleFormDialog {...defaultProps} open onSaved={vi.fn()} />);
    fireEvent.click(
      screen.getByRole("button", { name: /Criar agendamento/i }),
    );
    expect(
      await screen.findByText(/cron_expr invalida: XYZ/i),
    ).toBeInTheDocument();
  });

  it("403 mostra mensagem clara de permissao", async () => {
    createScheduleMock.mockRejectedValueOnce(new ApiError(403, null));
    render(<ScheduleFormDialog {...defaultProps} open onSaved={vi.fn()} />);
    fireEvent.click(
      screen.getByRole("button", { name: /Criar agendamento/i }),
    );
    expect(
      await screen.findByText(/nao tem permissao/i),
    ).toBeInTheDocument();
  });

  it("edicao pre-preenche o formulario e chama updateSchedule", async () => {
    const editing = {
      id: "s-1",
      tenant_id: "t-1",
      company_id: "c-1",
      cron_expr: "0 6 * * 1",
      timezone: "UTC",
      enabled: true,
      last_run_at: null,
      next_run_at: "2026-04-20T06:00:00Z",
      created_by_user_id: null,
      created_at: "2026-04-13T10:00:00Z",
      updated_at: "2026-04-13T10:00:00Z",
    };
    updateScheduleMock.mockResolvedValueOnce({
      ...editing,
      cron_expr: "0 6 * * 2",
    });
    render(
      <ScheduleFormDialog
        {...defaultProps}
        editing={editing}
        open
        onSaved={vi.fn()}
      />,
    );
    // Modo weekly detectado e cron preview carrega.
    expect(screen.getByTestId("cron-preview")).toHaveTextContent("0 6 * * 1");
    fireEvent.click(
      screen.getByRole("button", { name: /Salvar alteracoes/i }),
    );
    await waitFor(() =>
      expect(updateScheduleMock).toHaveBeenCalledWith(
        "s-1",
        expect.objectContaining({
          cron_expr: "0 6 * * 1",
          timezone: "UTC",
          company_id: "c-1",
          enabled: true,
        }),
        expect.anything(),
      ),
    );
  });
});
