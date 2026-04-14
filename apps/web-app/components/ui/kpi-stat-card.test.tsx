import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { FileText } from "lucide-react";

import { KPIStatCard } from "./kpi-stat-card";

const TREND_UP = [10, 12, 14, 13, 18, 22, 25];
const TREND_DOWN = [25, 22, 18, 17, 12, 10, 8];
const TREND_FLAT = [20, 21, 20, 22, 20, 21, 20];

describe("KPIStatCard", () => {
  it("snapshot: ready sem delta e sem sparkline", () => {
    const { container } = render(
      <KPIStatCard
        title="NFS-e coletadas (30d)"
        value="1.284"
        icon={FileText}
        hint="vs 30 dias anteriores"
      />,
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("snapshot: ready com delta positivo e sparkline", () => {
    const { container } = render(
      <KPIStatCard
        title="Taxa de sucesso"
        value="97,2%"
        deltaPercent={12.4}
        trendData={TREND_UP}
        icon={FileText}
        hint="vs 30 dias anteriores"
      />,
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("snapshot: ready com delta negativo e sparkline", () => {
    const { container } = render(
      <KPIStatCard
        title="Taxa de sucesso"
        value="83,1%"
        deltaPercent={-4.7}
        trendData={TREND_DOWN}
        icon={FileText}
        hint="vs 30 dias anteriores"
      />,
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("snapshot: ready com delta zero (estavel)", () => {
    const { container } = render(
      <KPIStatCard
        title="Coletas em andamento"
        value="6"
        deltaPercent={0}
        trendData={TREND_FLAT}
        icon={FileText}
        hint="vs 30 dias anteriores"
      />,
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("snapshot: loading", () => {
    const { container } = render(
      <KPIStatCard title="Carregando" state="loading" icon={FileText} />,
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("snapshot: empty", () => {
    const { container } = render(
      <KPIStatCard
        title="NFS-e coletadas (30d)"
        state="empty"
        icon={FileText}
        hint="Nenhuma coleta no periodo"
      />,
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("snapshot: error", () => {
    const { container } = render(
      <KPIStatCard
        title="NFS-e coletadas (30d)"
        state="error"
        icon={FileText}
        errorMessage="API indisponivel. Tente novamente."
      />,
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("usa o title como aria-label por padrao", () => {
    const { getByRole } = render(
      <KPIStatCard title="Certificados ativos" value="12" />,
    );
    expect(getByRole("article")).toHaveAttribute(
      "aria-label",
      "Certificados ativos",
    );
  });

  it("marca aria-busy quando em loading", () => {
    const { getByRole } = render(
      <KPIStatCard title="Carregando" state="loading" />,
    );
    expect(getByRole("article")).toHaveAttribute("aria-busy", "true");
  });

  it("ignora trendData com menos de 2 pontos", () => {
    const { container } = render(
      <KPIStatCard
        title="Singleton"
        value="1"
        deltaPercent={1}
        trendData={[10]}
      />,
    );
    // Sparkline usa role="presentation"; icone do delta e aria-hidden sem role.
    expect(container.querySelector('svg[role="presentation"]')).toBeNull();
  });
});
