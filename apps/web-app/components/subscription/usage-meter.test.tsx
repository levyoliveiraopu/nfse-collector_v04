import { describe, expect, it } from "vitest";
import { render, within } from "@testing-library/react";
import { Building2 } from "lucide-react";

import { UsageMeter } from "./usage-meter";

describe("<UsageMeter />", () => {
  it("renderiza titulo em uppercase, valor used/limit e percentual", () => {
    const { getByLabelText, getByText } = render(
      <UsageMeter
        title="CNPJs cadastrados"
        metric={{ used: 3, limit: 10 }}
        icon={Building2}
      />,
    );
    const card = getByLabelText("CNPJs cadastrados");
    expect(within(card).getByText("3")).toBeInTheDocument();
    expect(within(card).getByText(/\/ 10/)).toBeInTheDocument();
    expect(getByText("(30%)")).toBeInTheDocument();
  });

  it("expoe progressbar com aria-valuenow=used e aria-valuemax=limit", () => {
    const { getByRole } = render(
      <UsageMeter
        title="Execucoes"
        metric={{ used: 420, limit: 500 }}
        icon={Building2}
      />,
    );
    const bar = getByRole("progressbar");
    expect(bar.getAttribute("aria-valuenow")).toBe("420");
    expect(bar.getAttribute("aria-valuemax")).toBe("500");
    expect(bar.getAttribute("aria-valuemin")).toBe("0");
    expect(bar.getAttribute("aria-label")).toBe("Execucoes: 420 de 500");
  });

  it("marca data-tone=ok quando uso < 80%", () => {
    const { getByLabelText } = render(
      <UsageMeter
        title="Empresas"
        metric={{ used: 3, limit: 10 }}
        icon={Building2}
      />,
    );
    expect(getByLabelText("Empresas").getAttribute("data-tone")).toBe("ok");
  });

  it("marca data-tone=warn quando uso >= 80% e < 100%", () => {
    const { getByLabelText } = render(
      <UsageMeter
        title="Empresas"
        metric={{ used: 8, limit: 10 }}
        icon={Building2}
      />,
    );
    expect(getByLabelText("Empresas").getAttribute("data-tone")).toBe("warn");
  });

  it("marca data-tone=full quando used === limit", () => {
    const { getByLabelText } = render(
      <UsageMeter
        title="Usuarios"
        metric={{ used: 5, limit: 5 }}
        icon={Building2}
      />,
    );
    expect(getByLabelText("Usuarios").getAttribute("data-tone")).toBe("full");
  });

  it("clampa a largura da barra em 100% mesmo quando used > limit", () => {
    const { container } = render(
      <UsageMeter
        title="Over"
        metric={{ used: 15, limit: 10 }}
        icon={Building2}
      />,
    );
    const fill = container.querySelector("[role=progressbar] > div") as
      | HTMLElement
      | null;
    expect(fill).not.toBeNull();
    expect(fill!.style.width).toBe("100%");
  });

  it("lida com limit=0 sem divisao por zero (tone=ok, percent='-')", () => {
    const { getByLabelText, getByText } = render(
      <UsageMeter
        title="Zero"
        metric={{ used: 0, limit: 0 }}
        icon={Building2}
      />,
    );
    expect(getByLabelText("Zero").getAttribute("data-tone")).toBe("ok");
    expect(getByText("(-)")).toBeInTheDocument();
  });
});
