import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { Timeline, type TimelineItem } from "./timeline";

const ITEMS: TimelineItem[] = [
  {
    id: "1",
    timestamp: "2026-04-17T09:00:00Z",
    title: "Execucao iniciada",
    description: "tenant acme",
    tone: "info",
  },
  {
    id: "2",
    timestamp: "2026-04-17T09:05:00Z",
    title: "Coleta concluida",
    tone: "success",
  },
  {
    id: "3",
    timestamp: "2026-04-17T09:06:00Z",
    title: "Falha ao gerar XLSX",
    tone: "destructive",
  },
];

describe("Timeline", () => {
  it("renderiza todos os itens em ordem", () => {
    render(<Timeline items={ITEMS} />);
    const list = screen.getByRole("list");
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("Execucao iniciada");
    expect(items[1]).toHaveTextContent("Coleta concluida");
    expect(items[2]).toHaveTextContent("Falha ao gerar XLSX");
  });

  it("aria-label customizavel", () => {
    render(<Timeline items={ITEMS} ariaLabel="Execucoes recentes" />);
    expect(screen.getByRole("list")).toHaveAttribute(
      "aria-label",
      "Execucoes recentes",
    );
  });

  it("<time> usa ISO em dateTime", () => {
    const { container } = render(<Timeline items={ITEMS} />);
    const times = container.querySelectorAll("time");
    expect(times[0]).toHaveAttribute("dateTime", "2026-04-17T09:00:00Z");
    expect(times[1]).toHaveAttribute("dateTime", "2026-04-17T09:05:00Z");
  });

  it("aplica data-tone por item", () => {
    render(<Timeline items={ITEMS} />);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveAttribute("data-tone", "info");
    expect(items[1]).toHaveAttribute("data-tone", "success");
    expect(items[2]).toHaveAttribute("data-tone", "destructive");
  });

  it("lista vazia nao quebra", () => {
    const { container } = render(<Timeline items={[]} />);
    expect(container.querySelectorAll("li")).toHaveLength(0);
  });
});
