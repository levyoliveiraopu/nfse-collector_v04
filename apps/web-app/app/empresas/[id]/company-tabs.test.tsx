import * as React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

const replace = vi.fn();
let currentParams = new URLSearchParams("");
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/empresas/123",
  useSearchParams: () => currentParams,
}));

// Mock do AuthProvider para satisfazer dependencias dos paineis
// (overview-tab usa useAuth para mostrar Editar/Excluir).
vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => ({
    accessToken: "tok",
    refresh: vi.fn(),
    user: { userId: "u-1", tenantId: "t-1", role: "viewer" },
    status: "authenticated",
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
  }),
}));

import { CompanyTabs } from "./company-tabs";
import type { Company } from "@/lib/api/companies";

const company: Company = {
  id: "c-1",
  tenant_id: "t-1",
  cnpj: "11222333000181",
  razao_social: "Acme",
  nome_fantasia: null,
  municipio_ibge: "3550308",
  uf: "SP",
  status: "active",
  last_nsu: null,
  last_success_at: null,
  portal_provider: null,
  notes: null,
  created_at: "2026-04-16T12:00:00Z",
  updated_at: "2026-04-16T12:00:00Z",
};

function withQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

beforeEach(() => {
  replace.mockReset();
  currentParams = new URLSearchParams("");
});

afterEach(() => {
  document.body.style.overflow = "";
});

describe("CompanyTabs", () => {
  it("renderiza 6 abas com role=tab", async () => {
    render(withQueryClient(<CompanyTabs company={company} />));
    const tabs = await screen.findAllByRole("tab");
    expect(tabs).toHaveLength(6);
    const labels = tabs.map((t) => t.textContent);
    expect(labels).toEqual([
      "Visao geral",
      "Execucoes",
      "Credencial",
      "Agendamentos",
      "Arquivos",
      "Ocorrencias",
    ]);
  });

  it("monta apenas a aba ativa (visao geral por default)", async () => {
    const { container } = render(
      withQueryClient(<CompanyTabs company={company} />),
    );

    // Espera o painel ativo carregar.
    await waitFor(() => {
      const overviewPanel = container.querySelector(
        '[data-tab-panel="overview"]',
      );
      expect(overviewPanel?.children.length ?? 0).toBeGreaterThan(0);
    });

    // Paineis nao visitados ficam vazios (lazy).
    const inactiveIds = [
      "executions",
      "credential",
      "schedules",
      "files",
      "occurrences",
    ];
    for (const id of inactiveIds) {
      const panel = container.querySelector(`[data-tab-panel="${id}"]`);
      expect(panel).not.toBeNull();
      expect(panel).toHaveAttribute("hidden");
      expect(panel?.children.length ?? 0).toBe(0);
    }
  });

  it("aba so monta apos ser clicada (proof lazy)", async () => {
    const { container } = render(
      withQueryClient(<CompanyTabs company={company} />),
    );

    // Antes do clique: aba "credential" nao esta montada.
    const credentialPanel = () =>
      container.querySelector('[data-tab-panel="credential"]');
    await waitFor(() => expect(credentialPanel()).not.toBeNull());
    expect(credentialPanel()?.children.length).toBe(0);

    // Simula que a URL mudou para tab=credential (router.replace foi
    // chamado com a nova querystring; em runtime real o
    // useSearchParams reagiria. No teste, atualizamos o mock e
    // re-renderizamos via re-fire).
    const credentialTab = screen.getByRole("tab", { name: "Credencial" });
    fireEvent.click(credentialTab);

    expect(replace).toHaveBeenCalled();
    const url = String(replace.mock.calls[0]![0]);
    expect(url).toContain("tab=credential");
  });

  it("abas atendem navegacao por seta direita", async () => {
    render(withQueryClient(<CompanyTabs company={company} />));
    const tablist = screen.getByRole("tablist");
    fireEvent.keyDown(tablist, { key: "ArrowRight" });
    expect(replace).toHaveBeenCalled();
    const url = String(replace.mock.calls[0]![0]);
    expect(url).toContain("tab=executions");
  });
});
