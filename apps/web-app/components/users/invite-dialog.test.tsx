import * as React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const { toastSuccess, toastError } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: toastSuccess, error: toastError, info: vi.fn() },
}));

import { InviteDialog } from "./invite-dialog";

describe("<InviteDialog>", () => {
  beforeEach(() => {
    toastSuccess.mockReset();
    toastError.mockReset();
  });

  it("nao renderiza quando open=false", () => {
    render(
      <InviteDialog
        open={false}
        onClose={vi.fn()}
        actorRole="owner"
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("submete email + role e chama onClose + toast.success", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    render(
      <InviteDialog
        open
        onClose={onClose}
        actorRole="owner"
        onSubmit={onSubmit}
      />,
    );

    const email = screen.getByLabelText("Email") as HTMLInputElement;
    fireEvent.change(email, { target: { value: "novo@tenant.com" } });

    fireEvent.click(screen.getByRole("button", { name: /enviar convite/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith({
      email: "novo@tenant.com",
      role: "owner",
    });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(toastSuccess).toHaveBeenCalledWith(
      expect.stringContaining("novo@tenant.com"),
    );
  });

  it("rejeita email invalido (nao chama onSubmit)", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <InviteDialog
        open
        onClose={vi.fn()}
        actorRole="owner"
        onSubmit={onSubmit}
      />,
    );
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "lixo" },
    });
    fireEvent.click(screen.getByRole("button", { name: /enviar convite/i }));
    await waitFor(() =>
      expect(
        screen.getByText(/email valido/i),
      ).toBeInTheDocument(),
    );
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("admin nao ve opcao 'owner' no select de role", () => {
    render(
      <InviteDialog
        open
        onClose={vi.fn()}
        actorRole="admin"
        onSubmit={vi.fn()}
      />,
    );
    const select = screen.getByLabelText(
      /papel do usuario convidado/i,
    ) as HTMLSelectElement;
    const values = Array.from(select.options).map((o) => o.value);
    expect(values).not.toContain("owner");
    expect(values).not.toContain("admin");
    expect(values).toContain("operator");
    expect(values).toContain("viewer");
  });

  it("exibe toast.error quando onSubmit rejeita", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error("email ja usado"));
    render(
      <InviteDialog
        open
        onClose={vi.fn()}
        actorRole="owner"
        onSubmit={onSubmit}
      />,
    );
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "x@y.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /enviar convite/i }));
    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("email ja usado"),
    );
  });
});
