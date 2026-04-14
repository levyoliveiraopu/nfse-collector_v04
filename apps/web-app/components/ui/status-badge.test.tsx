import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import {
  STATUS_BADGE_VARIANTS,
  StatusBadge,
  type StatusBadgeSize,
} from "./status-badge";

const SIZES: StatusBadgeSize[] = ["sm", "md"];

describe("StatusBadge", () => {
  it("expoe as 10 variantes esperadas", () => {
    expect(STATUS_BADGE_VARIANTS).toEqual([
      "success",
      "processing",
      "pending",
      "failed",
      "warning",
      "blocked",
      "cert_expiring",
      "cred_invalid",
      "portal_unstable",
      "reprocess_needed",
    ]);
  });

  it.each(
    STATUS_BADGE_VARIANTS.flatMap((variant) =>
      SIZES.map((size) => [variant, size] as const),
    ),
  )("snapshot: variante %s tamanho %s", (variant, size) => {
    const { container } = render(
      <StatusBadge variant={variant} size={size} />,
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("permite sobrescrever label e tooltip", () => {
    const { getByRole } = render(
      <StatusBadge
        variant="success"
        label="Processou 12 notas"
        tooltip="12 NFS-e emitidas com sucesso"
      />,
    );
    const badge = getByRole("status");
    expect(badge).toHaveTextContent("Processou 12 notas");
    expect(badge).toHaveAttribute("title", "12 NFS-e emitidas com sucesso");
  });

  it("omite o icone quando hideIcon = true", () => {
    const { container } = render(
      <StatusBadge variant="failed" hideIcon />,
    );
    expect(container.querySelector("svg")).toBeNull();
  });
});
