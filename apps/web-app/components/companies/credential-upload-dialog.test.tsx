import { describe, expect, it, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

import { CredentialUploadDialog } from "./credential-upload-dialog";
import { CredentialApiError, type Credential } from "@/lib/companies/credentials";

function makePfx(name = "cert.pfx", size = 2048): File {
  const file = new File(["x".repeat(Math.min(size, 1024))], name, {
    type: "application/x-pkcs12",
  });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

function fakeCred(): Credential {
  return {
    id: "c1",
    tenant_id: "t1",
    company_id: "co1",
    type: "pfx_a1",
    pfx_object_key: "tenants-credentials/t1/c1.pfx.enc",
    cert_fingerprint: "aa".repeat(32),
    cert_not_before: "2026-01-01T00:00:00Z",
    cert_not_after: "2027-01-01T00:00:00Z",
    status: "active",
    cn_matches_cnpj: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

describe("<CredentialUploadDialog>", () => {
  it("nao renderiza quando open=false", () => {
    render(
      <CredentialUploadDialog
        open={false}
        onClose={() => {}}
        onUpload={async () => fakeCred()}
      />,
    );
    expect(
      screen.queryByRole("dialog", { name: /atualizar credencial/i }),
    ).toBeNull();
  });

  it("submit feliz: chama onUpload com file+password e fecha", async () => {
    const onUpload = vi.fn(async () => fakeCred());
    const onClose = vi.fn();
    const onUploaded = vi.fn();

    render(
      <CredentialUploadDialog
        open
        onClose={onClose}
        onUpload={onUpload}
        onUploaded={onUploaded}
      />,
    );

    // Injeta o arquivo direto no input hidden do FileDropzone.
    const file = makePfx();
    const inputs = screen
      .getByRole("dialog")
      .querySelectorAll<HTMLInputElement>('input[type="file"]');
    expect(inputs.length).toBe(1);
    await act(async () => {
      fireEvent.change(inputs[0], { target: { files: [file] } });
    });

    const password = screen.getByPlaceholderText(/digite a senha/i);
    fireEvent.change(password, { target: { value: "secret" } });

    const submit = screen.getByRole("button", { name: /enviar credencial/i });
    await act(async () => {
      fireEvent.click(submit);
    });

    await waitFor(() => {
      expect(onUpload).toHaveBeenCalledTimes(1);
    });
    expect(onUpload).toHaveBeenCalledWith({
      file: expect.any(File),
      password: "secret",
    });
    expect(onUploaded).toHaveBeenCalledWith(fakeCred());
    expect(onClose).toHaveBeenCalled();
  });

  it("erro 400 (senha incorreta) exibe mensagem acionavel e nao fecha", async () => {
    const err = new CredentialApiError(
      400,
      "invalid_password_or_pfx",
      "senha incorreta",
    );
    const onUpload = vi.fn(async () => {
      throw err;
    });
    const onClose = vi.fn();

    render(
      <CredentialUploadDialog open onClose={onClose} onUpload={onUpload} />,
    );
    const inputs = screen
      .getByRole("dialog")
      .querySelectorAll<HTMLInputElement>('input[type="file"]');
    await act(async () => {
      fireEvent.change(inputs[0], { target: { files: [makePfx()] } });
    });
    fireEvent.change(screen.getByPlaceholderText(/digite a senha/i), {
      target: { value: "wrong" },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /enviar credencial/i }));
    });

    await waitFor(() => {
      expect(screen.getByTestId("credential-upload-error")).toHaveTextContent(
        /senha incorreta|pfx invalido/i,
      );
    });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("erro 413 exibe mensagem sobre limite do servidor", async () => {
    const onUpload = vi.fn(async () => {
      throw new CredentialApiError(413, "pfx_too_large", "grande");
    });
    render(
      <CredentialUploadDialog open onClose={() => {}} onUpload={onUpload} />,
    );
    const inputs = screen
      .getByRole("dialog")
      .querySelectorAll<HTMLInputElement>('input[type="file"]');
    await act(async () => {
      fireEvent.change(inputs[0], { target: { files: [makePfx()] } });
    });
    fireEvent.change(screen.getByPlaceholderText(/digite a senha/i), {
      target: { value: "x" },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /enviar credencial/i }));
    });
    await waitFor(() => {
      expect(screen.getByTestId("credential-upload-error")).toHaveTextContent(
        /excede/i,
      );
    });
  });

  it("botao submit desabilita ate ter file + senha", async () => {
    render(
      <CredentialUploadDialog
        open
        onClose={() => {}}
        onUpload={async () => fakeCred()}
      />,
    );
    const submit = screen.getByRole("button", {
      name: /enviar credencial/i,
    }) as HTMLButtonElement;
    expect(submit.disabled).toBe(true);

    const inputs = screen
      .getByRole("dialog")
      .querySelectorAll<HTMLInputElement>('input[type="file"]');
    await act(async () => {
      fireEvent.change(inputs[0], { target: { files: [makePfx()] } });
    });
    expect(submit.disabled).toBe(true); // falta senha

    fireEvent.change(screen.getByPlaceholderText(/digite a senha/i), {
      target: { value: "s" },
    });
    expect(submit.disabled).toBe(false);
  });
});
