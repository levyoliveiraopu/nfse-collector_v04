import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HelpButton } from "./help-button";
import { HelpPanel } from "./help-panel";
import { HelpProvider } from "./help-provider";

const state = vi.hoisted(() => ({ pathname: "/dashboard" }));
const recordHelpEvent = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));

vi.mock("next/navigation", () => ({
  usePathname: () => state.pathname,
}));

vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => ({
    status: "authenticated",
    user: { userId: "u-1", tenantId: "t-1", role: "operator" },
    accessToken: "token",
    refresh: vi.fn().mockResolvedValue(true),
  }),
}));

vi.mock("@/lib/api/help", () => ({ recordHelpEvent }));

function Harness() {
  return (
    <HelpProvider>
      <HelpButton />
      <HelpPanel />
    </HelpProvider>
  );
}

describe("contextual help", () => {
  beforeEach(() => {
    state.pathname = "/dashboard";
    recordHelpEvent.mockClear();
    window.localStorage.clear();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        text: async () => "## Como usar\n\nOrientação segura.",
      }),
    );
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn().mockReturnValue({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    });
  });

  it("shows Novo once and opens the route article accessibly", async () => {
    render(<Harness />);
    expect(screen.getByText("Novo")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /abrir ajuda/i }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.queryByText("Novo")).not.toBeInTheDocument();
    expect(
      window.localStorage.getItem("nfse:help:opened:t-1:u-1:v1"),
    ).toBe("1");
    await waitFor(() =>
      expect(recordHelpEvent).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          event_type: "article_opened",
          article_slug: "dashboard",
          route_key: "dashboard",
        }),
      ),
    );
  });

  it("keeps the panel open and updates the article after navigation", async () => {
    const view = render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: /abrir ajuda/i }));
    expect(await screen.findByText("Dashboard")).toBeInTheDocument();

    await act(async () => {
      state.pathname = "/agendamentos";
      view.rerender(<Harness />);
    });

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Agendamentos" }),
    ).toBeInTheDocument();
  });

  it("records helpful feedback once without sending free text", async () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: /abrir ajuda/i }));
    const yes = await screen.findByRole("button", { name: "Sim" });
    fireEvent.click(yes);

    expect(screen.getByText("Obrigado pela resposta.")).toBeInTheDocument();
    expect(recordHelpEvent).toHaveBeenCalledWith(
      expect.anything(),
      {
        event_type: "feedback_yes",
        article_slug: "dashboard",
        route_key: "dashboard",
      },
    );
  });

  it("closes the desktop panel with Escape and restores trigger focus", async () => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn().mockReturnValue({
        matches: true,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    });
    render(<Harness />);
    const trigger = screen.getByRole("button", { name: /abrir ajuda/i });

    fireEvent.click(trigger);
    expect(
      await screen.findByRole("complementary", { name: "Ajuda contextual" }),
    ).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() =>
      expect(
        screen.queryByRole("complementary", { name: "Ajuda contextual" }),
      ).not.toBeInTheDocument(),
    );
    await waitFor(() => expect(trigger).toHaveFocus());
  });
});
