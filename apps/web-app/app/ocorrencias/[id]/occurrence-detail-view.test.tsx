import * as React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/ocorrencias/occ-1",
  useSearchParams: () => new URLSearchParams(""),
}));

const useAuthMock = vi.fn();
vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => useAuthMock(),
}));

// Stub do ReactMarkdown: apenas renderiza o texto cru como <article>
// para nao depender da cadeia remark/unified no ambiente jsdom.
vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => (
    <article data-testid="markdown">{children}</article>
  ),
}));
vi.mock("remark-gfm", () => ({ default: () => null }));

const apiMock = vi.hoisted(() => ({
  getOccurrence: vi.fn(),
  acknowledgeOccurrence: vi.fn(),
  resolveOccurrence: vi.fn(),
  assignOccurrence: vi.fn(),
}));

vi.mock("@/lib/api/occurrences", async () => {
  const actual = await vi.importActual<
    typeof import("@/lib/api/occurrences")
  >("@/lib/api/occurrences");
  return {
    ...actual,
    getOccurrence: apiMock.getOccurrence,
    acknowledgeOccurrence: apiMock.acknowledgeOccurrence,
    resolveOccurrence: apiMock.resolveOccurrence,
    assignOccurrence: apiMock.assignOccurrence,
  };
});

import { OccurrenceDetailView } from "./occurrence-detail-view";

function fakeOccurrence(overrides: Record<string, unknown> = {}) {
  return {
    id: "occ-1",
    tenant_id: "t-1",
    company_id: "c-1",
    execution_id: null,
    severity: "error",
    code: "CERT_EXPIRED",
    title: "Certificado A1 expirado",
    detail: "notAfter=2024-01-01",
    status: "open",
    assignee_user_id: null,
    first_seen_at: "2026-04-17T10:00:00Z",
    last_seen_at: "2026-04-17T10:00:00Z",
    resolved_at: null,
    created_at: "2026-04-17T10:00:00Z",
    updated_at: "2026-04-17T10:00:00Z",
    ...overrides,
  };
}

function mountAsRole(role: string) {
  useAuthMock.mockReturnValue({
    accessToken: "tok",
    refresh: vi.fn(),
    user: { userId: "u-1", tenantId: "t-1", role },
    status: "authenticated",
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <OccurrenceDetailView occurrenceId="occ-1" />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  useAuthMock.mockReset();
  apiMock.getOccurrence.mockReset();
  apiMock.acknowledgeOccurrence.mockReset();
  apiMock.resolveOccurrence.mockReset();
  apiMock.assignOccurrence.mockReset();
  // fetch do runbook — mockado para nao bater em /api/runbooks durante
  // os testes.
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      new Response("# Runbook teste", {
        status: 200,
        headers: { "content-type": "text/markdown" },
      }),
    ),
  );
});

describe("OccurrenceDetailView", () => {
  it("renderiza header com codigo e severity, carrega via getOccurrence", async () => {
    apiMock.getOccurrence.mockResolvedValueOnce(fakeOccurrence());
    mountAsRole("operator");

    expect(
      await screen.findByRole("heading", {
        name: /Certificado A1 expirado/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("CERT_EXPIRED")).toBeInTheDocument();
    expect(apiMock.getOccurrence).toHaveBeenCalledWith(
      "occ-1",
      expect.objectContaining({ accessToken: "tok" }),
    );
  });

  it("oculta acoes mutadoras para viewer", async () => {
    apiMock.getOccurrence.mockResolvedValueOnce(fakeOccurrence());
    mountAsRole("viewer");

    await screen.findByRole("heading", {
      name: /Certificado A1 expirado/i,
    });
    expect(
      screen.queryByRole("button", { name: /Reconhecer/i }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: /^Resolver$/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /Atribuir/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /Reprocessar/i })).toBeNull();
  });

  it("acknowledge chama a API e atualiza cache sem reload", async () => {
    apiMock.getOccurrence.mockResolvedValueOnce(fakeOccurrence());
    apiMock.acknowledgeOccurrence.mockResolvedValueOnce(
      fakeOccurrence({ status: "ack" }),
    );

    mountAsRole("operator");
    const btn = await screen.findByRole("button", { name: /Reconhecer/i });
    await act(async () => {
      fireEvent.click(btn);
    });

    await waitFor(() =>
      expect(apiMock.acknowledgeOccurrence).toHaveBeenCalledWith(
        "occ-1",
        expect.anything(),
      ),
    );
    // Apos sucesso, a ocorrencia vira ack -> botao de reconhecer somem.
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: /Reconhecer/i }),
      ).toBeNull(),
    );
  });

  it("reprocessar vira link para /execucoes/nova com query params", async () => {
    apiMock.getOccurrence.mockResolvedValueOnce(fakeOccurrence());
    mountAsRole("admin");
    const link = (await screen.findByRole("link", {
      name: /Reprocessar/i,
    })) as HTMLAnchorElement;
    expect(link.getAttribute("href")).toMatch(/\/execucoes\/nova/);
    expect(link.getAttribute("href")).toMatch(/reprocessar_de=occ-1/);
    expect(link.getAttribute("href")).toMatch(/company_id=c-1/);
  });

  it("nao mostra 'Resolver' nem 'Reconhecer' em estado terminal", async () => {
    apiMock.getOccurrence.mockResolvedValueOnce(
      fakeOccurrence({ status: "resolved", resolved_at: "2026-04-17T11:00:00Z" }),
    );
    mountAsRole("owner");
    await screen.findByRole("heading", {
      name: /Certificado A1 expirado/i,
    });
    expect(
      screen.queryByRole("button", { name: /Reconhecer/i }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: /^Resolver$/i })).toBeNull();
    // Atribuir continua disponivel (API-09 nao bloqueia assign em terminal).
    expect(
      screen.getByRole("button", { name: /Atribuir/i }),
    ).toBeInTheDocument();
  });
});
