import * as React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";

// Mock de next/navigation antes de importar a DataTable.
const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/styleguide",
  useSearchParams: () => new URLSearchParams(""),
}));

import { DataTable } from "./data-table";
import type { FetchParams, FetchResult } from "./types";

interface Row {
  id: number;
  name: string;
}

const columns: ColumnDef<Row, unknown>[] = [
  { id: "id", accessorKey: "id", header: "ID" },
  { id: "name", accessorKey: "name", header: "Nome" },
];

function withQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

beforeEach(() => {
  replace.mockReset();
  window.localStorage.clear();
});

describe("DataTable", () => {
  it("renderiza skeleton enquanto carrega", async () => {
    let resolve: (v: FetchResult<Row>) => void = () => {};
    const fetcher = vi.fn(
      () => new Promise<FetchResult<Row>>((r) => (resolve = r)),
    );

    const { container } = render(
      withQueryClient(
        <DataTable<Row>
          queryKey="t1"
          columns={columns}
          fetcher={fetcher}
        />,
      ),
    );

    // tbody aria-busy durante fetch inicial.
    expect(container.querySelector("tbody")).toHaveAttribute("aria-busy");
    // Existem celulas esqueleto (pulse).
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(
      0,
    );

    // Resolve para nao vazar promise.
    resolve({ rows: [], total: 0 });
  });

  it("renderiza estado vazio quando total = 0", async () => {
    const fetcher = vi.fn(
      async (): Promise<FetchResult<Row>> => ({ rows: [], total: 0 }),
    );
    render(
      withQueryClient(
        <DataTable<Row>
          queryKey="t2"
          columns={columns}
          fetcher={fetcher}
          emptyMessage="Sem registros."
        />,
      ),
    );
    await waitFor(() =>
      expect(screen.getByText("Sem registros.")).toBeInTheDocument(),
    );
  });

  it("renderiza linhas vindas do fetcher", async () => {
    const fetcher = vi.fn(
      async (): Promise<FetchResult<Row>> => ({
        rows: [
          { id: 1, name: "Alice" },
          { id: 2, name: "Bob" },
        ],
        total: 2,
      }),
    );
    render(
      withQueryClient(
        <DataTable<Row> queryKey="t3" columns={columns} fetcher={fetcher} />,
      ),
    );
    expect(await screen.findByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
    // Contagem "1-2 de 2".
    expect(screen.getByText(/1-2 de 2/)).toBeInTheDocument();
  });

  it("exibe erro com botao 'Tentar novamente' que chama refetch", async () => {
    const fetcher = vi
      .fn<(params: FetchParams) => Promise<FetchResult<Row>>>()
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce({
        rows: [{ id: 1, name: "Alice" }],
        total: 1,
      });
    render(
      withQueryClient(
        <DataTable<Row> queryKey="t4" columns={columns} fetcher={fetcher} />,
      ),
    );
    const retry = await screen.findByRole("button", {
      name: /tentar novamente/i,
    });
    expect(screen.getByRole("alert")).toHaveTextContent("boom");
    fireEvent.click(retry);
    expect(await screen.findByText("Alice")).toBeInTheDocument();
  });

  it("clica em proxima pagina e chama router.replace com page=2", async () => {
    const fetcher = vi.fn(
      async (): Promise<FetchResult<Row>> => ({
        rows: [{ id: 1, name: "Alice" }],
        total: 100,
      }),
    );
    render(
      withQueryClient(
        <DataTable<Row>
          queryKey="t5"
          columns={columns}
          fetcher={fetcher}
          defaultPageSize={25}
        />,
      ),
    );
    await screen.findByText("Alice");
    const next = screen.getByRole("button", { name: /proxima pagina/i });
    fireEvent.click(next);
    expect(replace).toHaveBeenCalled();
    const url = replace.mock.calls[0]![0] as string;
    expect(url).toContain("page=2");
  });
});
