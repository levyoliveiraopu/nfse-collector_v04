import * as React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
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

const listCompaniesMock = vi.fn();
vi.mock("@/lib/api/companies", async () => {
  const actual = await vi.importActual<
    typeof import("@/lib/api/companies")
  >("@/lib/api/companies");
  return {
    ...actual,
    listCompanies: (...args: unknown[]) => listCompaniesMock(...args),
  };
});

const fetchCredentialMock = vi.fn();
vi.mock("@/lib/companies/credentials", async () => {
  const actual = await vi.importActual<
    typeof import("@/lib/companies/credentials")
  >("@/lib/companies/credentials");
  return {
    ...actual,
    fetchCredential: (...args: unknown[]) => fetchCredentialMock(...args),
    uploadCredential: vi.fn(),
    revokeCredential: vi.fn(),
  };
});

const listExecutionsMock = vi.fn();
vi.mock("@/lib/api/executions", async () => {
  const actual = await vi.importActual<
    typeof import("@/lib/api/executions")
  >("@/lib/api/executions");
  return {
    ...actual,
    listExecutions: (...args: unknown[]) => listExecutionsMock(...args),
    getExecution: vi.fn(),
    createExecutions: vi.fn(),
  };
});

vi.mock("@/lib/api/onboarding", () => ({
  postFirstCollectionDone: vi.fn(),
}));

import { OnboardingWizard } from "./onboarding-wizard";
import type { Company } from "@/lib/api/companies";

function withQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

const authed = (role = "owner") => ({
  accessToken: "tok",
  refresh: vi.fn(),
  user: { userId: "u-1", tenantId: "t-1", role },
  status: "authenticated" as const,
  login: vi.fn(),
  signup: vi.fn(),
  logout: vi.fn(),
});

function makeCompany(overrides: Partial<Company> = {}): Company {
  return {
    id: "c-1",
    tenant_id: "t-1",
    cnpj: "11222333000181",
    razao_social: "Acme LTDA",
    nome_fantasia: null,
    municipio_ibge: "3550308",
    uf: "SP",
    status: "active",
    last_nsu: null,
    last_success_at: null,
    portal_provider: null,
    notes: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function setLocalStorage() {
  const store = new Map<string, string>();
  const storage: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (k) => store.get(k) ?? null,
    key: (i) => Array.from(store.keys())[i] ?? null,
    removeItem: (k) => {
      store.delete(k);
    },
    setItem: (k, v) => {
      store.set(k, v);
    },
  };
  Object.defineProperty(window, "localStorage", {
    value: storage,
    configurable: true,
  });
  return storage;
}

beforeEach(() => {
  useAuthMock.mockReset();
  listCompaniesMock.mockReset();
  fetchCredentialMock.mockReset();
  listExecutionsMock.mockReset();
  setLocalStorage();
});

describe("<OnboardingWizard>", () => {
  it("nao renderiza quando sessao nao esta autenticada", async () => {
    useAuthMock.mockReturnValue({
      ...authed(),
      user: null,
      status: "unauthenticated",
    });
    render(withQueryClient(<OnboardingWizard />));
    expect(screen.queryByTestId("onboarding-wizard")).toBeNull();
  });

  it("mostra passo 1 (empresa) quando o tenant nao tem empresas", async () => {
    useAuthMock.mockReturnValue(authed());
    listCompaniesMock.mockResolvedValue({ rows: [], total: 0 });
    fetchCredentialMock.mockResolvedValue(null);
    listExecutionsMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 1,
      total: 0,
    });

    render(withQueryClient(<OnboardingWizard />));

    await waitFor(() => {
      expect(screen.getByTestId("onboarding-wizard")).toBeInTheDocument();
    });
    expect(screen.getByTestId("onboarding-step-empresa")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /cadastre sua primeira empresa/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("onboarding-skip")).toBeInTheDocument();
  });

  it("mostra passo 2 (credencial) quando ha empresa mas sem credencial ativa", async () => {
    useAuthMock.mockReturnValue(authed());
    const company = makeCompany();
    listCompaniesMock.mockResolvedValue({ rows: [company], total: 1 });
    fetchCredentialMock.mockResolvedValue(null);
    listExecutionsMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 1,
      total: 0,
    });

    render(withQueryClient(<OnboardingWizard />));

    await waitFor(() => {
      expect(screen.getByTestId("onboarding-step-credencial")).toBeInTheDocument();
    });
    expect(
      screen.getByRole("heading", { name: /certificado digital a1/i }),
    ).toBeInTheDocument();
  });

  it("mostra passo 3 (execucao) quando tem empresa e credencial ativa mas nenhuma coleta ok", async () => {
    useAuthMock.mockReturnValue(authed("operator"));
    const company = makeCompany();
    listCompaniesMock.mockResolvedValue({ rows: [company], total: 1 });
    fetchCredentialMock.mockResolvedValue({
      id: "cr-1",
      tenant_id: "t-1",
      company_id: company.id,
      type: "pfx_a1",
      pfx_object_key: "x",
      cert_fingerprint: "aa".repeat(32),
      cert_not_before: "2026-01-01T00:00:00Z",
      cert_not_after: "2030-01-01T00:00:00Z",
      status: "active",
      cn_matches_cnpj: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
    listExecutionsMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 1,
      total: 0,
    });

    render(withQueryClient(<OnboardingWizard />));

    await waitFor(() => {
      expect(screen.getByTestId("onboarding-step-execucao")).toBeInTheDocument();
    });
    expect(
      screen.getByRole("button", { name: /iniciar 1a coleta/i }),
    ).toBeInTheDocument();
  });

  it("nao renderiza quando onboarding esta completo (ja tem succeeded)", async () => {
    useAuthMock.mockReturnValue(authed());
    const company = makeCompany();
    listCompaniesMock.mockResolvedValue({ rows: [company], total: 1 });
    fetchCredentialMock.mockResolvedValue({
      id: "cr-1",
      tenant_id: "t-1",
      company_id: company.id,
      type: "pfx_a1",
      pfx_object_key: "x",
      cert_fingerprint: null,
      cert_not_before: null,
      cert_not_after: null,
      status: "active",
      cn_matches_cnpj: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
    listExecutionsMock.mockImplementation(async (params: { status?: string }) => ({
      items: [],
      page: 1,
      page_size: 1,
      total: params.status === "succeeded" ? 1 : 0,
    }));

    render(withQueryClient(<OnboardingWizard />));

    // Aguarda as queries terminarem e confirma que o wizard nao aparece.
    await waitFor(() => {
      expect(listExecutionsMock).toHaveBeenCalled();
    });
    expect(screen.queryByTestId("onboarding-wizard")).toBeNull();
  });

  it("botao 'Pular por enquanto' fecha o wizard e registra dismiss em localStorage", async () => {
    useAuthMock.mockReturnValue(authed());
    listCompaniesMock.mockResolvedValue({ rows: [], total: 0 });
    fetchCredentialMock.mockResolvedValue(null);
    listExecutionsMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 1,
      total: 0,
    });

    const { container } = render(withQueryClient(<OnboardingWizard />));
    await waitFor(() => {
      expect(screen.getByTestId("onboarding-wizard")).toBeInTheDocument();
    });

    await act(async () => {
      screen.getByTestId("onboarding-skip").click();
    });

    await waitFor(() => {
      expect(container.querySelector('[data-testid="onboarding-wizard"]')).toBeNull();
    });

    // Verifica o flag persistido.
    expect(
      window.localStorage.getItem("nfse:onboarding:dismissed:t-1:u-1"),
    ).toBeTruthy();
  });

  it("nao reabre se o dismiss estiver ativo (ultimas 24h)", async () => {
    useAuthMock.mockReturnValue(authed());
    listCompaniesMock.mockResolvedValue({ rows: [], total: 0 });
    fetchCredentialMock.mockResolvedValue(null);
    listExecutionsMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 1,
      total: 0,
    });

    window.localStorage.setItem(
      "nfse:onboarding:dismissed:t-1:u-1",
      String(Date.now()),
    );

    render(withQueryClient(<OnboardingWizard />));
    // Dummy wait para as queries resolverem mesmo assim.
    await waitFor(() => {
      expect(listCompaniesMock).toHaveBeenCalled();
    });
    expect(screen.queryByTestId("onboarding-wizard")).toBeNull();
  });

  it("reabre se o dismiss expirou (>24h)", async () => {
    useAuthMock.mockReturnValue(authed());
    listCompaniesMock.mockResolvedValue({ rows: [], total: 0 });
    fetchCredentialMock.mockResolvedValue(null);
    listExecutionsMock.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 1,
      total: 0,
    });

    // 48h atras.
    const expired = Date.now() - 48 * 60 * 60 * 1000;
    window.localStorage.setItem(
      "nfse:onboarding:dismissed:t-1:u-1",
      String(expired),
    );

    render(withQueryClient(<OnboardingWizard />));

    await waitFor(() => {
      expect(screen.getByTestId("onboarding-wizard")).toBeInTheDocument();
    });
  });
});
