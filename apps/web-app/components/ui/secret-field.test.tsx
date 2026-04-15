import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, waitFor } from "@testing-library/react";

import { SecretField } from "./secret-field";

describe("SecretField", () => {
  beforeEach(() => {
    // Mocka Clipboard API (jsdom nao expoe por padrao).
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it("renderiza como password por padrao", () => {
    const { container } = render(<SecretField defaultValue="segredo" />);
    const input = container.querySelector("input")!;
    expect(input.type).toBe("password");
  });

  it("alterna type=password <-> text no botao Mostrar/Ocultar", () => {
    const { container, getByLabelText } = render(
      <SecretField defaultValue="senha-forte" />,
    );
    const input = container.querySelector("input")!;

    fireEvent.click(getByLabelText("Mostrar"));
    expect(input.type).toBe("text");

    fireEvent.click(getByLabelText("Ocultar"));
    expect(input.type).toBe("password");
  });

  it("chama clipboard.writeText e emite onCopy", async () => {
    const onCopy = vi.fn();
    const { getByLabelText, getByRole } = render(
      <SecretField defaultValue="abc123" onCopy={onCopy} />,
    );

    fireEvent.click(getByLabelText("Copiar"));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith("abc123");
    });
    expect(onCopy).toHaveBeenCalledWith("abc123");
    // Mensagem de status aparece apos copia bem-sucedida.
    expect(getByRole("status")).toHaveTextContent(/copiado/i);
  });

  it("desabilita o botao Copiar quando vazio", () => {
    const { getByLabelText } = render(<SecretField />);
    expect(getByLabelText("Copiar")).toBeDisabled();
  });

  it("respeita allowReveal=false e allowCopy=false", () => {
    const { queryByLabelText } = render(
      <SecretField defaultValue="x" allowReveal={false} allowCopy={false} />,
    );
    expect(queryByLabelText("Mostrar")).toBeNull();
    expect(queryByLabelText("Copiar")).toBeNull();
  });

  it("chama onCopyError quando o clipboard falha", async () => {
    const err = new Error("denied");
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockRejectedValue(err) },
    });
    const onCopyError = vi.fn();
    const { getByLabelText } = render(
      <SecretField defaultValue="x" onCopyError={onCopyError} />,
    );
    fireEvent.click(getByLabelText("Copiar"));
    await waitFor(() => {
      expect(onCopyError).toHaveBeenCalledWith(err);
    });
  });
});
