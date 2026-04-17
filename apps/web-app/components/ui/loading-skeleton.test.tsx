import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import { LoadingSkeleton } from "./loading-skeleton";

describe("LoadingSkeleton", () => {
  it("expoe aria-busy e aria-label customizavel", () => {
    const { getByRole } = render(<LoadingSkeleton ariaLabel="Buscando..." />);
    const region = getByRole("status");
    expect(region).toHaveAttribute("aria-busy", "true");
    expect(region).toHaveAttribute("aria-label", "Buscando...");
  });

  it("variante lines: renderiza N barras", () => {
    const { container } = render(<LoadingSkeleton lines={5} />);
    const region = container.querySelector('[data-variant="lines"]');
    expect(region).not.toBeNull();
    expect(region!.querySelectorAll("div.animate-pulse").length).toBe(5);
  });

  it("variante rows: renderiza rows x columns barras", () => {
    const { container } = render(
      <LoadingSkeleton rows={3} columns={4} />,
    );
    const region = container.querySelector('[data-variant="rows"]');
    expect(region).not.toBeNull();
    expect(region!.querySelectorAll("div.animate-pulse").length).toBe(12);
  });

  it("rows tem prioridade sobre lines quando ambos definidos", () => {
    const { container } = render(
      <LoadingSkeleton lines={10} rows={2} columns={2} />,
    );
    const region = container.querySelector('[data-variant="rows"]');
    expect(region).not.toBeNull();
    expect(region!.querySelectorAll("div.animate-pulse").length).toBe(4);
  });
});
