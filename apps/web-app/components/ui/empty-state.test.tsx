import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Inbox } from "lucide-react";

import { EmptyState } from "./empty-state";

describe("EmptyState", () => {
  it("renderiza titulo e descricao", () => {
    render(
      <EmptyState title="Sem empresas" description="Cadastre para comecar." />,
    );
    expect(screen.getByText("Sem empresas")).toBeInTheDocument();
    expect(screen.getByText("Cadastre para comecar.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute(
      "aria-label",
      "Sem empresas",
    );
  });

  it("renderiza icone Lucide quando fornecido", () => {
    const { container } = render(
      <EmptyState title="Caixa vazia" icon={Inbox} />,
    );
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("action.onClick dispara ao clicar no CTA", () => {
    const onClick = vi.fn();
    render(
      <EmptyState
        title="Sem dados"
        action={{ label: "Recarregar", onClick }}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Recarregar" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("action.href renderiza link em vez de botao", () => {
    render(
      <EmptyState
        title="Sem empresas"
        action={{ label: "Cadastrar", href: "/empresas/nova" }}
      />,
    );
    const link = screen.getByRole("link", { name: "Cadastrar" });
    expect(link).toHaveAttribute("href", "/empresas/nova");
  });
});
