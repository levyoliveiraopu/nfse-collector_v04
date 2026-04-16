import { describe, expect, it } from "vitest";
import { render, within } from "@testing-library/react";

import AssinaturaPage from "./page";
import { MOCK_SUBSCRIPTION } from "@/lib/subscription/mock";

describe("AssinaturaPage (APP-10)", () => {
  it("renderiza o nome do plano atribuido e status 'Ativo'", () => {
    const { getByText, getByRole } = render(<AssinaturaPage />);
    expect(getByText(MOCK_SUBSCRIPTION.plan.name)).toBeInTheDocument();
    // StatusBadge usa role="status" com aria-label = "Ativo".
    expect(getByRole("status", { name: "Ativo" })).toBeInTheDocument();
  });

  it("renderiza os 3 cards de uso com used/limit e barra de progresso", () => {
    const { getByLabelText } = render(<AssinaturaPage />);
    const cnpjs = getByLabelText("CNPJs cadastrados");
    const execucoes = getByLabelText("Execucoes no mes");
    const usuarios = getByLabelText("Usuarios");

    expect(
      within(cnpjs).getByText(String(MOCK_SUBSCRIPTION.usage.companies.used)),
    ).toBeInTheDocument();
    expect(
      within(cnpjs).getByText(
        new RegExp(`/ ${MOCK_SUBSCRIPTION.usage.companies.limit}`),
      ),
    ).toBeInTheDocument();
    expect(within(execucoes).getByRole("progressbar")).toBeInTheDocument();
    expect(within(usuarios).getByRole("progressbar")).toBeInTheDocument();
  });

  it("marca o card de usuarios como tone=full quando used === limit", () => {
    const { getByLabelText } = render(<AssinaturaPage />);
    const usuarios = getByLabelText("Usuarios");
    // Mock tem users: 5/5 -> tone === "full".
    expect(usuarios).toHaveAttribute("data-tone", "full");
  });

  it("mostra a mensagem de contato com suporte e links WhatsApp + email", () => {
    const { getByText, getByRole } = render(<AssinaturaPage />);
    expect(
      getByText("Para alterar plano, entre em contato com o suporte."),
    ).toBeInTheDocument();

    const whatsapp = getByRole("link", { name: /whatsapp/i });
    expect(whatsapp).toHaveAttribute("href", expect.stringMatching(/^https:\/\/wa\.me\//));

    const email = getByRole("link", { name: /suporte@/i });
    expect(email).toHaveAttribute("href", expect.stringMatching(/^mailto:/));
  });

  it("NAO renderiza botao/link de upgrade (reforca cobranca manual — ADR-004)", () => {
    const { queryByRole } = render(<AssinaturaPage />);
    // Prova defensiva: nenhum control com textos tipicos de upgrade.
    expect(queryByRole("button", { name: /upgrade/i })).toBeNull();
    expect(queryByRole("link", { name: /upgrade/i })).toBeNull();
    expect(queryByRole("button", { name: /fazer upgrade/i })).toBeNull();
    expect(queryByRole("button", { name: /assinar/i })).toBeNull();
    expect(queryByRole("button", { name: /mudar plano/i })).toBeNull();
  });

  it("exibe placeholder vazio de historico de faturas", () => {
    const { getByLabelText, getByText } = render(<AssinaturaPage />);
    const historico = getByLabelText("Historico de faturas");
    expect(historico).toBeInTheDocument();
    expect(
      within(historico).getByText("Nenhuma fatura registrada ate o momento."),
    ).toBeInTheDocument();
    // E a copy principal — "Nenhuma fatura..." — existe no DOM.
    expect(getByText(/Historico de faturas/i)).toBeInTheDocument();
  });
});
