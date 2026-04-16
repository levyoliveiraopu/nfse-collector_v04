import { describe, expect, it, vi } from "vitest";

import {
  CredentialApiError,
  decideCredentialBadge,
  fetchCredential,
  formatFingerprint,
  revokeCredential,
  uploadCredential,
  type Credential,
} from "./credentials";
import { ApiError } from "@/lib/auth/api-client";

function fakeCred(overrides: Partial<Credential> = {}): Credential {
  return {
    id: "c1",
    tenant_id: "t1",
    company_id: "co1",
    type: "pfx_a1",
    pfx_object_key: "tenants-credentials/t1/c1.pfx.enc",
    cert_fingerprint:
      "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6",
    cert_not_before: "2026-01-01T00:00:00Z",
    cert_not_after: "2027-01-01T00:00:00Z",
    status: "active",
    cn_matches_cnpj: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("formatFingerprint", () => {
  it("formata em grupos de 2 separados por `:` (padrao OpenSSL)", () => {
    expect(formatFingerprint("a1b2c3d4")).toBe("a1:b2:c3:d4");
  });

  it("normaliza para lowercase e remove separadores existentes", () => {
    expect(formatFingerprint("A1:B2:C3")).toBe("a1:b2:c3");
  });

  it("devolve vazio para ausencia ou valor nao-hex", () => {
    expect(formatFingerprint(null)).toBe("");
    expect(formatFingerprint("")).toBe("");
    expect(formatFingerprint("xxx")).toBe("");
  });
});

describe("decideCredentialBadge", () => {
  const NOW = new Date("2026-04-15T12:00:00Z");

  it("credencial ausente -> pending", () => {
    const d = decideCredentialBadge(null, NOW);
    expect(d.variant).toBe("pending");
    expect(d.daysUntilExpiry).toBeNull();
  });

  it("ativa com validade > 30d -> success", () => {
    const d = decideCredentialBadge(
      fakeCred({ cert_not_after: "2027-04-15T12:00:00Z" }),
      NOW,
    );
    expect(d.variant).toBe("success");
    expect(d.label).toBe("Ativa");
  });

  it("ativa vencendo em <= 30d -> cert_expiring com contador", () => {
    const d = decideCredentialBadge(
      fakeCred({ cert_not_after: "2026-05-05T12:00:00Z" }), // 20d
      NOW,
    );
    expect(d.variant).toBe("cert_expiring");
    expect(d.daysUntilExpiry).toBe(20);
    expect(d.label).toContain("20");
  });

  it("ativa apos not_after -> failed (expirada)", () => {
    const d = decideCredentialBadge(
      fakeCred({ cert_not_after: "2026-01-01T00:00:00Z" }),
      NOW,
    );
    expect(d.variant).toBe("failed");
    expect(d.label).toBe("Expirada");
  });

  it("revoked -> blocked", () => {
    const d = decideCredentialBadge(fakeCred({ status: "revoked" }), NOW);
    expect(d.variant).toBe("blocked");
  });

  it("invalid -> cred_invalid", () => {
    const d = decideCredentialBadge(fakeCred({ status: "invalid" }), NOW);
    expect(d.variant).toBe("cred_invalid");
  });
});

// ---------------------------------------------------------------------------
// HTTP — mockamos `fetch` global (apiFetch usa window.fetch).
// ---------------------------------------------------------------------------

function mockFetch(implementation: (url: string, init: RequestInit) => Response | Promise<Response>) {
  const spy = vi.fn(async (url: string, init: RequestInit) => implementation(url, init));
  vi.stubGlobal("fetch", spy);
  return spy;
}

describe("fetchCredential", () => {
  it("devolve null em 404 (nao configurada)", async () => {
    mockFetch(() => new Response("{\"detail\":\"credencial nao configurada\"}", { status: 404 }));
    const out = await fetchCredential("co1", { accessToken: "tok" });
    expect(out).toBeNull();
  });

  it("parseia e devolve a credencial em 200", async () => {
    const cred = fakeCred();
    mockFetch(
      () =>
        new Response(JSON.stringify(cred), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    const out = await fetchCredential("co1", { accessToken: "tok" });
    expect(out).toEqual(cred);
  });

  it("erro 403 vira CredentialApiError(forbidden)", async () => {
    mockFetch(() => new Response("{}", { status: 403 }));
    await expect(fetchCredential("co1", { accessToken: "tok" })).rejects.toMatchObject({
      code: "forbidden",
      status: 403,
    });
  });
});

describe("uploadCredential", () => {
  it("envia multipart `pfx` + `password` e devolve a credencial", async () => {
    const cred = fakeCred();
    const spy = mockFetch(async (url, init) => {
      expect(url).toContain("/companies/co1/credential");
      expect(init.method).toBe("POST");
      expect(init.body).toBeInstanceOf(FormData);
      const form = init.body as FormData;
      expect(form.get("password")).toBe("secret");
      expect(form.get("pfx")).toBeInstanceOf(File);
      return new Response(JSON.stringify(cred), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    });
    const file = new File(["x".repeat(10)], "cert.pfx", {
      type: "application/x-pkcs12",
    });
    const out = await uploadCredential(
      "co1",
      { file, password: "secret" },
      { accessToken: "tok" },
    );
    expect(out).toEqual(cred);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("mapeia 400 `senha incorreta` para invalid_password_or_pfx", async () => {
    mockFetch(
      () =>
        new Response(
          JSON.stringify({ detail: "pfx invalido ou senha incorreta" }),
          { status: 400, headers: { "Content-Type": "application/json" } },
        ),
    );
    const file = new File(["x"], "cert.pfx");
    await expect(
      uploadCredential("co1", { file, password: "x" }, { accessToken: "t" }),
    ).rejects.toMatchObject({ code: "invalid_password_or_pfx", status: 400 });
  });

  it("mapeia 413 para pfx_too_large", async () => {
    mockFetch(() => new Response("{}", { status: 413 }));
    const file = new File(["x"], "cert.pfx");
    await expect(
      uploadCredential("co1", { file, password: "x" }, { accessToken: "t" }),
    ).rejects.toMatchObject({ code: "pfx_too_large", status: 413 });
  });

  it("mapeia 502 para storage_failed", async () => {
    mockFetch(() => new Response("{}", { status: 502 }));
    const file = new File(["x"], "cert.pfx");
    await expect(
      uploadCredential("co1", { file, password: "x" }, { accessToken: "t" }),
    ).rejects.toMatchObject({ code: "storage_failed", status: 502 });
  });

  it("preserva CredentialApiError quando lancado diretamente", () => {
    const original = new CredentialApiError(400, "pfx_empty", "vazio");
    expect(original).toBeInstanceOf(CredentialApiError);
    expect(original).toBeInstanceOf(Error);
    expect(original.code).toBe("pfx_empty");
  });
});

describe("revokeCredential", () => {
  it("devolve a lista de IDs revogados", async () => {
    mockFetch(
      () =>
        new Response(JSON.stringify({ revoked: ["c1"] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    const out = await revokeCredential("co1", { accessToken: "t" });
    expect(out.revoked).toEqual(["c1"]);
  });

  it("mapeia 404 sem ativa para not_configured", async () => {
    mockFetch(
      () =>
        new Response(
          JSON.stringify({ detail: "nenhuma credencial ativa para revogar" }),
          { status: 404, headers: { "Content-Type": "application/json" } },
        ),
    );
    await expect(revokeCredential("co1", { accessToken: "t" })).rejects.toMatchObject({
      code: "not_configured",
      status: 404,
    });
  });
});

// Cobre a construtora direta de ApiError (import usado no module).
describe("ApiError interop", () => {
  it("ApiError de 401 vira unauthorized", async () => {
    mockFetch(() => new Response("{}", { status: 401 }));
    await expect(revokeCredential("co1", { accessToken: "t" })).rejects.toMatchObject({
      code: "unauthorized",
      status: 401,
    });
  });

  it("garante que ApiError e reexportavel do modulo auth", () => {
    const err = new ApiError(400, { detail: "x" });
    expect(err.status).toBe(400);
  });
});
