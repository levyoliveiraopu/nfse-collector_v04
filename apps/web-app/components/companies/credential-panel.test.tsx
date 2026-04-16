import { describe, expect, it, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

import { CredentialPanel } from "./credential-panel";
import { AuthProvider } from "@/components/auth/auth-provider";
import type { Credential } from "@/lib/companies/credentials";

function fakeCred(overrides: Partial<Credential> = {}): Credential {
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
    ...overrides,
  };
}

/**
 * O AuthProvider chama `/api/auth/refresh` ao montar. Fazemos um stub
 * generico de fetch que devolve 401 pra qualquer chamada que nao seja
 * explicitamente mockada — forca o provider a ir pra status
 * "unauthenticated", que nao atende o RequireAuth. Mas o CredentialPanel
 * nao depende de RequireAuth aqui; roda isolado.
 *
 * Para simular usuario `owner`, mockamos `/api/auth/refresh` retornando
 * uma sessao valida.
 */
function stubSession(role: string = "owner") {
  const fetchSpy = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url.endsWith("/api/auth/refresh")) {
      return new Response(
        JSON.stringify({
          access_token: "tok",
          expires_in: 900,
          user: { userId: "u1", tenantId: "t1", role },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    return new Response("{}", { status: 404 });
  });
  vi.stubGlobal("fetch", fetchSpy);
  return fetchSpy;
}

async function renderAuthed(role: string, ui: React.ReactElement) {
  stubSession(role);
  const result = render(<AuthProvider>{ui}</AuthProvider>);
  // Aguarda provider rehidratar.
  await waitFor(() => {
    // botao "Atualizar credencial" so renderiza depois de status=authenticated.
    expect(
      screen.getByRole("button", { name: /atualizar credencial/i }),
    ).toBeInTheDocument();
  });
  return result;
}

describe("<CredentialPanel>", () => {
  it("render inicial: loading -> ready com credencial ativa", async () => {
    const cred = fakeCred();
    const fetchFn = vi.fn(async () => cred);
    await renderAuthed(
      "owner",
      <CredentialPanel
        companyId="co1"
        clientOverrides={{ fetch: fetchFn }}
      />,
    );
    await waitFor(() => expect(fetchFn).toHaveBeenCalled());
    expect(fetchFn).toHaveBeenCalledWith("co1", expect.objectContaining({ accessToken: "tok" }));
    // Badge "Ativa" aparece.
    await waitFor(() =>
      expect(screen.getByRole("status", { name: /ativa/i })).toBeInTheDocument(),
    );
  });

  it("estado nao configurada: revogar fica desabilitado", async () => {
    const fetchFn = vi.fn(async () => null);
    await renderAuthed(
      "owner",
      <CredentialPanel
        companyId="co1"
        clientOverrides={{ fetch: fetchFn }}
      />,
    );
    await waitFor(() => expect(fetchFn).toHaveBeenCalled());
    const revoke = screen.getByRole("button", { name: /revogar/i }) as HTMLButtonElement;
    expect(revoke.disabled).toBe(true);
  });

  it("viewer: botoes de escrita desabilitados", async () => {
    const fetchFn = vi.fn(async () => fakeCred());
    await renderAuthed(
      "viewer",
      <CredentialPanel
        companyId="co1"
        clientOverrides={{ fetch: fetchFn }}
      />,
    );
    const update = screen.getByRole("button", {
      name: /atualizar credencial/i,
    }) as HTMLButtonElement;
    const revoke = screen.getByRole("button", { name: /revogar/i }) as HTMLButtonElement;
    expect(update.disabled).toBe(true);
    expect(revoke.disabled).toBe(true);
  });

  it("upload feliz: atualiza badge para ativa e fecha dialog", async () => {
    const fetchFn = vi.fn(async () => null); // inicial: sem credencial
    const uploadFn = vi.fn(async () => fakeCred());
    await renderAuthed(
      "owner",
      <CredentialPanel
        companyId="co1"
        clientOverrides={{ fetch: fetchFn, upload: uploadFn }}
      />,
    );
    await waitFor(() => expect(fetchFn).toHaveBeenCalled());

    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: /atualizar credencial/i }),
      );
    });

    const dialog = await screen.findByRole("dialog", {
      name: /atualizar credencial/i,
    });
    const fileInput = dialog.querySelector<HTMLInputElement>('input[type="file"]')!;
    const file = new File(["x"], "cert.pfx", {
      type: "application/x-pkcs12",
    });
    Object.defineProperty(file, "size", { value: 2048 });
    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });
    fireEvent.change(screen.getByPlaceholderText(/digite a senha/i), {
      target: { value: "secret" },
    });
    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: /enviar credencial/i }),
      );
    });

    await waitFor(() => expect(uploadFn).toHaveBeenCalledTimes(1));
    expect(uploadFn).toHaveBeenCalledWith(
      "co1",
      { file: expect.any(File), password: "secret" },
      expect.objectContaining({ accessToken: "tok" }),
    );
    // Badge reflete credencial ativa.
    await waitFor(() =>
      expect(screen.getByRole("status", { name: /ativa/i })).toBeInTheDocument(),
    );
  });

  it("revogar: confirma via REVOGAR e volta ao estado nao configurada", async () => {
    const fetchFn = vi.fn(async () => fakeCred());
    const revokeFn = vi.fn(async () => ({ revoked: ["c1"] }));
    await renderAuthed(
      "owner",
      <CredentialPanel
        companyId="co1"
        clientOverrides={{ fetch: fetchFn, revoke: revokeFn }}
      />,
    );
    await waitFor(() =>
      expect(screen.getByRole("status", { name: /ativa/i })).toBeInTheDocument(),
    );

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /revogar/i }));
    });
    const input = await screen.findByLabelText(/digite/i);
    fireEvent.change(input, { target: { value: "REVOGAR" } });
    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: /revogar credencial/i }),
      );
    });

    await waitFor(() => expect(revokeFn).toHaveBeenCalledTimes(1));
    // Badge volta para "Nao configurada".
    await waitFor(() =>
      expect(
        screen.getByRole("status", { name: /nao configurada/i }),
      ).toBeInTheDocument(),
    );
  });

  it("erro de fetch inicial mostra 'Tentar novamente' e refaz", async () => {
    let calls = 0;
    const fetchFn = vi.fn(async () => {
      calls++;
      if (calls === 1) throw new Error("boom");
      return fakeCred();
    });
    await renderAuthed(
      "owner",
      <CredentialPanel
        companyId="co1"
        clientOverrides={{ fetch: fetchFn }}
      />,
    );
    await waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(1));
    const retry = await screen.findByRole("button", { name: /tentar novamente/i });
    await act(async () => {
      fireEvent.click(retry);
    });
    await waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(screen.getByRole("status", { name: /ativa/i })).toBeInTheDocument(),
    );
  });

  it("'Testar agora' sempre desabilitado (aguarda endpoint futuro)", async () => {
    const fetchFn = vi.fn(async () => fakeCred());
    await renderAuthed(
      "owner",
      <CredentialPanel
        companyId="co1"
        clientOverrides={{ fetch: fetchFn }}
      />,
    );
    const test = screen.getByRole("button", { name: /testar agora/i }) as HTMLButtonElement;
    expect(test.disabled).toBe(true);
  });
});
