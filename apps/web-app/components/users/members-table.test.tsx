import * as React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

import { MembersTable } from "./members-table";
import type { Member } from "@/lib/users/types";

const BASE_MEMBER: Member = {
  userId: "u-1",
  email: "owner@demo.local",
  name: "Owner Original",
  role: "owner",
  status: "active",
  lastLoginAt: "2026-04-10T12:00:00Z",
  createdAt: "2026-01-01T00:00:00Z",
};

const SECONDARY: Member = {
  userId: "u-2",
  email: "beltrano@demo.local",
  name: "Beltrano Silva",
  role: "operator",
  status: "active",
  lastLoginAt: null,
  createdAt: "2026-02-01T00:00:00Z",
};

describe("<MembersTable>", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renderiza lista vazia", () => {
    render(
      <MembersTable
        members={[]}
        actorRole="owner"
        actorUserId="u-0"
        onChangeRole={vi.fn()}
        onRemove={vi.fn()}
      />,
    );
    expect(
      screen.getByText(/nenhum usuario cadastrado/i),
    ).toBeInTheDocument();
  });

  it("renderiza linhas com role e email", () => {
    render(
      <MembersTable
        members={[BASE_MEMBER, SECONDARY]}
        actorRole="owner"
        actorUserId="u-0"
        onChangeRole={vi.fn()}
        onRemove={vi.fn()}
      />,
    );
    expect(screen.getByText("Owner Original")).toBeInTheDocument();
    expect(screen.getByText("owner@demo.local")).toBeInTheDocument();
    expect(screen.getByText("Beltrano Silva")).toBeInTheDocument();
    expect(screen.getByText(/nunca/i)).toBeInTheDocument();
  });

  it("admin ve botao de acoes desabilitado para o owner alheio", () => {
    render(
      <MembersTable
        members={[BASE_MEMBER]}
        actorRole="admin"
        actorUserId="admin-id"
        onChangeRole={vi.fn()}
        onRemove={vi.fn()}
      />,
    );
    const btn = screen.getByRole("button", {
      name: /acoes para owner original/i,
    }) as HTMLButtonElement;
    expect(btn).toBeDisabled();
    expect(btn.title).toMatch(/owner pode gerenciar outro owner/i);
  });

  it("ator nao consegue gerenciar a si mesmo", () => {
    render(
      <MembersTable
        members={[BASE_MEMBER]}
        actorRole="owner"
        actorUserId={BASE_MEMBER.userId}
        onChangeRole={vi.fn()}
        onRemove={vi.fn()}
      />,
    );
    const btn = screen.getByRole("button", {
      name: /acoes para owner original/i,
    });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute(
      "title",
      expect.stringMatching(/si mesmo/i),
    );
  });

  it("owner remove membro: abre confirm e chama onRemove", async () => {
    const onRemove = vi.fn().mockResolvedValue(undefined);
    render(
      <MembersTable
        members={[SECONDARY]}
        actorRole="owner"
        actorUserId="owner-id"
        onChangeRole={vi.fn()}
        onRemove={onRemove}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /acoes para beltrano silva/i }),
    );
    fireEvent.click(screen.getByRole("menuitem", { name: /remover usuario/i }));
    // Modal aberto com titulo "Remover usuario"
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remover" }));
    await waitFor(() =>
      expect(onRemove).toHaveBeenCalledWith(SECONDARY.userId),
    );
  });

  it("owner altera papel de operator para admin", async () => {
    const onChangeRole = vi.fn().mockResolvedValue(undefined);
    render(
      <MembersTable
        members={[SECONDARY]}
        actorRole="owner"
        actorUserId="owner-id"
        onChangeRole={onChangeRole}
        onRemove={vi.fn()}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /acoes para beltrano silva/i }),
    );
    fireEvent.click(screen.getByRole("menuitem", { name: /alterar papel/i }));
    const select = screen.getByLabelText(
      /novo papel do usuario/i,
    ) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "admin" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() =>
      expect(onChangeRole).toHaveBeenCalledWith(SECONDARY.userId, "admin"),
    );
  });
});
