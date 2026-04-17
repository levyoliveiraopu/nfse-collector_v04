import * as React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: pushMock, prefetch: vi.fn() }),
  usePathname: () => "/execucoes/nova",
  useSearchParams: () => new URLSearchParams(""),
}));

const useAuthMock = vi.fn();
vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => useAuthMock(),
}));

const listCompaniesMock = vi.fn();
vi.mock("@/lib/api/companies", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/companies")>(
    "@/lib/api/companies",
  );
  return {
    ...actual,
    listCompanies: (...args: unknown[]) =>
      (listCompaniesMock as (...a: unknown[]) => unknown)(...args),
  };
});

const createExecutionsMock = vi.fn();
vi.mock("@/lib/api/executions", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/executions")>(
    "@/lib/api/executions",
  );
  return {
    ...actual,
    createExecutions: (...args: unknown[]) =>
      (createExecutionsMock as (...a: unknown[]) => unknown)(...args),
  };
});

import { NovaExecucaoForm } from "./nova-execucao-form";
import { ExecutionsApiError } from "@/lib/api/executions";

function withClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

function authed(role: string) {
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

const company1 = {
  id: "c1",
  tenant_id: "t-1",
  cnpj: "12345678000190",
  razao_social: "Acme Ltda",
  nome_fantasia: null,
  municipio_ibge: "3550308",
  uf: "SP",
  status: "active" as const,
  last_nsu: 0,
  last_success_at: null,
  portal_provider: null,
  notes: null,
  created_at: "",
  updated_at: "",
};
const company2 = { ...company1, id: "c2", cnpj: "11222333000181", razao_social: "Beta Eireli" };

beforeEach(() => {
  pushMock.mockReset();
  useAuthMock.mockReset();
  listCompaniesMock.mockReset();
  createExecutionsMock.mockReset();
  listCompaniesMock.mockResolvedValue({ rows: [company1, company2], total: 2 });
});

describe("NovaExecucaoForm — gating por papel", () => {
  it("viewer ve alerta sem permissao", async () => {
    authed("viewer");
    render(withClient(<NovaExecucaoForm />));
    expect(
      await screen.findByText(/Sem permissao para criar execucoes/i),
    ).toBeInTheDocument();
  });

  it("operator ve o formulario", async () => {
    authed("operator");
    render(withClient(<NovaExecucaoForm />));
    expect(
      await screen.findByRole("button", { name: /iniciar/i }),
    ).toBeInTheDocument();
  });
});

describe("NovaExecucaoForm — submissao feliz", () => {
  it("enviando 1 empresa redireciona para /execucoes/{id}", async () => {
    authed("operator");
    createExecutionsMock.mockResolvedValueOnce({
      created: [
        {
          execution_id: "e1",
          company_id: "c1",
          status: "queued",
          job_id: "j1",
          enqueue_error: null,
        },
      ],
    });

    render(withClient(<NovaExecucaoForm />));

    const checkbox = await screen.findByRole("checkbox", {
      name: /Acme Ltda/i,
    });
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByRole("button", { name: /iniciar/i }));

    await waitFor(() => {
      expect(createExecutionsMock).toHaveBeenCalledTimes(1);
      expect(pushMock).toHaveBeenCalledWith("/execucoes/e1");
    });
    const payload = createExecutionsMock.mock.calls[0]![0];
    expect(payload.company_ids).toEqual(["c1"]);
    expect(payload.dry_run).toBe(false);
  });

  it("com N>1 empresas redireciona para /execucoes (lista)", async () => {
    authed("admin");
    createExecutionsMock.mockResolvedValueOnce({
      created: [
        { execution_id: "e1", company_id: "c1", status: "queued", job_id: "j1", enqueue_error: null },
        { execution_id: "e2", company_id: "c2", status: "queued", job_id: "j2", enqueue_error: null },
      ],
    });

    render(withClient(<NovaExecucaoForm />));
    const c1 = await screen.findByRole("checkbox", { name: /Acme Ltda/i });
    const c2 = await screen.findByRole("checkbox", { name: /Beta Eireli/i });
    fireEvent.click(c1);
    fireEvent.click(c2);
    fireEvent.click(screen.getByRole("button", { name: /iniciar/i }));
    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/execucoes");
    });
  });

  it("propaga dry_run quando toggle marcado", async () => {
    authed("operator");
    createExecutionsMock.mockResolvedValueOnce({
      created: [
        { execution_id: "e1", company_id: "c1", status: "queued", job_id: "j1", enqueue_error: null },
      ],
    });

    render(withClient(<NovaExecucaoForm />));
    fireEvent.click(await screen.findByRole("checkbox", { name: /Acme Ltda/i }));
    fireEvent.click(screen.getByLabelText(/Dry-run/i));
    fireEvent.click(screen.getByRole("button", { name: /iniciar/i }));
    await waitFor(() => {
      expect(createExecutionsMock).toHaveBeenCalledTimes(1);
    });
    expect(createExecutionsMock.mock.calls[0]![0].dry_run).toBe(true);
  });
});

describe("NovaExecucaoForm — erros", () => {
  it("traduz 422 credential_missing_or_expired em mensagem com CNPJs", async () => {
    authed("operator");
    createExecutionsMock.mockRejectedValueOnce(
      new ExecutionsApiError(422, "credential_missing_or_expired", "x", {
        companyIds: ["c1"],
      }),
    );

    render(withClient(<NovaExecucaoForm />));
    fireEvent.click(await screen.findByRole("checkbox", { name: /Acme Ltda/i }));
    fireEvent.click(screen.getByRole("button", { name: /iniciar/i }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent ?? "").toMatch(/credencial/i);
    expect(alert.textContent ?? "").toContain("12.345.678/0001-90");
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("502 queue_unavailable mostra mensagem de fila indisponivel", async () => {
    authed("operator");
    createExecutionsMock.mockRejectedValueOnce(
      new ExecutionsApiError(
        502,
        "queue_unavailable",
        "Fila de jobs indisponivel. Tente novamente em instantes.",
      ),
    );

    render(withClient(<NovaExecucaoForm />));
    fireEvent.click(await screen.findByRole("checkbox", { name: /Acme Ltda/i }));
    fireEvent.click(screen.getByRole("button", { name: /iniciar/i }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent ?? "").toMatch(/Fila.*indisponivel/i);
  });
});
