import * as React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/empresas",
  useSearchParams: () => new URLSearchParams(""),
}));

const useAuthMock = vi.fn();
vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => useAuthMock(),
}));

// EmpresasTable depende de listCompanies; mocka para nao bater na rede.
vi.mock("@/lib/api/companies", async () => {
  const actual = await vi.importActual<
    typeof import("@/lib/api/companies")
  >("@/lib/api/companies");
  return {
    ...actual,
    listCompanies: vi.fn(async () => ({ rows: [], total: 0 })),
  };
});

import { EmpresasView } from "./empresas-view";

function withQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

beforeEach(() => {
  useAuthMock.mockReset();
});

describe("EmpresasView (gating de acoes por papel)", () => {
  it("oculta botao 'Nova empresa' para viewer", () => {
    useAuthMock.mockReturnValue({
      accessToken: "tok",
      refresh: vi.fn(),
      user: { userId: "u-1", tenantId: "t-1", role: "viewer" },
      status: "authenticated",
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
    });
    render(withQueryClient(<EmpresasView />));
    expect(
      screen.queryByRole("button", { name: /nova empresa/i }),
    ).toBeNull();
  });

  it("mostra botao 'Nova empresa' para owner/admin/operator", () => {
    for (const role of ["owner", "admin", "operator"]) {
      useAuthMock.mockReturnValue({
        accessToken: "tok",
        refresh: vi.fn(),
        user: { userId: "u-1", tenantId: "t-1", role },
        status: "authenticated",
        login: vi.fn(),
        signup: vi.fn(),
        logout: vi.fn(),
      });
      const { unmount } = render(withQueryClient(<EmpresasView />));
      expect(
        screen.getByRole("button", { name: /nova empresa/i }),
      ).toBeInTheDocument();
      unmount();
    }
  });
});
