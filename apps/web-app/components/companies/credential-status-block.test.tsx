import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { CredentialStatusBlock } from "./credential-status-block";
import type { Credential } from "@/lib/companies/credentials";

const NOW = new Date("2026-04-15T12:00:00Z");

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
    cert_not_after: "2027-04-15T12:00:00Z",
    status: "active",
    cn_matches_cnpj: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("<CredentialStatusBlock>", () => {
  it("estado nao configurada: placeholder + badge pending", () => {
    render(<CredentialStatusBlock credential={null} now={NOW} />);
    expect(screen.getByText(/nenhum certificado a1/i)).toBeInTheDocument();
    expect(screen.getByRole("status", { name: /nao configurada/i })).toBeInTheDocument();
  });

  it("credencial ativa: fingerprint em grupos de 2 + badge success", () => {
    render(
      <CredentialStatusBlock credential={fakeCred()} now={NOW} />,
    );
    const fp = screen.getByTestId("credential-fingerprint");
    expect(fp.textContent).toMatch(/^a1:b2:c3:d4/);
    expect(fp.textContent).toContain(":");
    expect(screen.getByRole("status", { name: /ativa/i })).toBeInTheDocument();
    // Data formatada pt-BR.
    expect(screen.getByText("15/04/2027")).toBeInTheDocument();
  });

  it("cn mismatch + signal=true exibe alerta LGPD-style", () => {
    render(
      <CredentialStatusBlock
        credential={fakeCred({ cn_matches_cnpj: false })}
        now={NOW}
        cnMismatchWarning
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/cnpj/i);
  });

  it("sem sinal de mismatch, nao renderiza alerta mesmo com cn_matches_cnpj=false", () => {
    render(
      <CredentialStatusBlock
        credential={fakeCred({ cn_matches_cnpj: false })}
        now={NOW}
      />,
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("credencial vencendo em <30d mostra badge cert_expiring com contador", () => {
    render(
      <CredentialStatusBlock
        credential={fakeCred({ cert_not_after: "2026-05-05T12:00:00Z" })}
        now={NOW}
      />,
    );
    // 20 dias restantes.
    expect(screen.getByRole("status", { name: /expira em 20d/i })).toBeInTheDocument();
  });
});
