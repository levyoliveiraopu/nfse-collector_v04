import * as React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

import { PendingInvitations } from "./pending-invitations";
import type { Invitation } from "@/lib/users/types";

const PENDING: Invitation = {
  id: "inv-1",
  email: "novato@tenant.com",
  role: "operator",
  status: "pending",
  createdAt: "2026-04-10T10:00:00Z",
  expiresAt: "2026-04-17T10:00:00Z",
  invitedByEmail: "admin@tenant.com",
};

const ACCEPTED: Invitation = {
  ...PENDING,
  id: "inv-2",
  email: "ja-aceito@tenant.com",
  status: "accepted",
};

describe("<PendingInvitations>", () => {
  it("renderiza vazio quando nao ha pendentes (mesmo com accepted/revoked na lista)", () => {
    render(
      <PendingInvitations
        invitations={[ACCEPTED]}
        actorRole="owner"
        onRevoke={vi.fn()}
      />,
    );
    expect(screen.getByText(/nenhum convite pendente/i)).toBeInTheDocument();
  });

  it("exibe convite pendente e dispara onRevoke apos confirmar", async () => {
    const onRevoke = vi.fn().mockResolvedValue(undefined);
    render(
      <PendingInvitations
        invitations={[PENDING]}
        actorRole="owner"
        onRevoke={onRevoke}
      />,
    );
    expect(screen.getByText("novato@tenant.com")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: /revogar convite de novato/i }),
    );
    // Confirm dialog aberto
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Revogar" }));
    await waitFor(() => expect(onRevoke).toHaveBeenCalledWith("inv-1"));
  });

  it("exibe erro com 'Tentar novamente'", () => {
    const onRetry = vi.fn();
    render(
      <PendingInvitations
        invitations={[]}
        error="falha na rede"
        onRetry={onRetry}
        actorRole="owner"
        onRevoke={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("falha na rede");
    fireEvent.click(screen.getByRole("button", { name: /tentar novamente/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("nao-manager ve botao desabilitado", () => {
    render(
      <PendingInvitations
        invitations={[PENDING]}
        actorRole="viewer"
        onRevoke={vi.fn()}
      />,
    );
    const btn = screen.getByRole("button", {
      name: /revogar convite de novato/i,
    }) as HTMLButtonElement;
    expect(btn).toBeDisabled();
  });
});
