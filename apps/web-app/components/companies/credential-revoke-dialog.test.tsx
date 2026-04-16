import { describe, expect, it, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

import { CredentialRevokeDialog } from "./credential-revoke-dialog";
import { CredentialApiError } from "@/lib/companies/credentials";

describe("<CredentialRevokeDialog>", () => {
  it("submit bloqueado ate digitar REVOGAR", () => {
    const onRevoke = vi.fn(async () => ({ revoked: ["c1"] }));
    render(
      <CredentialRevokeDialog
        open
        onClose={() => {}}
        onRevoke={onRevoke}
      />,
    );
    const submit = screen.getByRole("button", {
      name: /revogar credencial/i,
    }) as HTMLButtonElement;
    expect(submit.disabled).toBe(true);

    const input = screen.getByLabelText(/digite/i);
    fireEvent.change(input, { target: { value: "revog" } });
    expect(submit.disabled).toBe(true);

    fireEvent.change(input, { target: { value: "REVOGAR" } });
    expect(submit.disabled).toBe(false);
  });

  it("aceita variante em minusculas (case-insensitive)", () => {
    render(
      <CredentialRevokeDialog
        open
        onClose={() => {}}
        onRevoke={async () => ({ revoked: [] })}
      />,
    );
    const submit = screen.getByRole("button", {
      name: /revogar credencial/i,
    }) as HTMLButtonElement;
    fireEvent.change(screen.getByLabelText(/digite/i), {
      target: { value: "revogar" },
    });
    expect(submit.disabled).toBe(false);
  });

  it("submit feliz chama onRevoke + onRevoked + onClose", async () => {
    const onRevoke = vi.fn(async () => ({ revoked: ["c1"] }));
    const onRevoked = vi.fn();
    const onClose = vi.fn();
    render(
      <CredentialRevokeDialog
        open
        onClose={onClose}
        onRevoke={onRevoke}
        onRevoked={onRevoked}
      />,
    );
    fireEvent.change(screen.getByLabelText(/digite/i), {
      target: { value: "REVOGAR" },
    });
    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: /revogar credencial/i }),
      );
    });
    await waitFor(() => {
      expect(onRevoke).toHaveBeenCalledTimes(1);
      expect(onRevoked).toHaveBeenCalledWith(["c1"]);
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("erro 404 (nenhuma ativa) mostra mensagem amigavel", async () => {
    const onRevoke = vi.fn(async () => {
      throw new CredentialApiError(404, "not_configured", "nada");
    });
    render(
      <CredentialRevokeDialog open onClose={() => {}} onRevoke={onRevoke} />,
    );
    fireEvent.change(screen.getByLabelText(/digite/i), {
      target: { value: "REVOGAR" },
    });
    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: /revogar credencial/i }),
      );
    });
    await waitFor(() => {
      expect(screen.getByTestId("credential-revoke-error")).toHaveTextContent(
        /nenhuma credencial ativa/i,
      );
    });
  });
});
