import { describe, expect, it, vi } from "vitest";
import { fireEvent, render } from "@testing-library/react";

import { PeriodPicker } from "./period-picker";

const TODAY = new Date(Date.UTC(2026, 3, 15, 12, 0, 0, 0)); // 2026-04-15

describe("PeriodPicker", () => {
  it("emite range correto para preset 'Mes atual'", () => {
    const onChange = vi.fn();
    const { getByText } = render(
      <PeriodPicker today={TODAY} onChange={onChange} />,
    );
    fireEvent.click(getByText("Mes atual"));
    expect(onChange).toHaveBeenCalledWith({
      from: "2026-04-01",
      to: "2026-04-15",
      preset: "current_month",
    });
  });

  it("emite range correto para 'Ultimos 7 dias'", () => {
    const onChange = vi.fn();
    const { getByText } = render(
      <PeriodPicker today={TODAY} onChange={onChange} />,
    );
    fireEvent.click(getByText("Ultimos 7 dias"));
    expect(onChange).toHaveBeenCalledWith({
      from: "2026-04-09",
      to: "2026-04-15",
      preset: "last_7d",
    });
  });

  it("marca preset selecionado com aria-pressed", () => {
    const { getByText } = render(<PeriodPicker today={TODAY} />);
    const btn = getByText("Mes anterior");
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-pressed")).toBe("true");
  });

  it("emite range custom quando datas validas e ordenadas", () => {
    const onChange = vi.fn();
    const { getByLabelText } = render(
      <PeriodPicker today={TODAY} onChange={onChange} />,
    );
    const from = getByLabelText("Data inicial") as HTMLInputElement;
    const to = getByLabelText("Data final") as HTMLInputElement;

    fireEvent.change(from, { target: { value: "2026-02-01" } });
    fireEvent.change(to, { target: { value: "2026-02-28" } });

    const calls = onChange.mock.calls;
    expect(calls[calls.length - 1][0]).toEqual({
      from: "2026-02-01",
      to: "2026-02-28",
      preset: "custom",
    });
  });

  it("mostra erro quando from > to e nao emite onChange", () => {
    const onChange = vi.fn();
    const { getByLabelText, getByRole } = render(
      <PeriodPicker
        today={TODAY}
        defaultValue={{
          from: "2026-04-01",
          to: "2026-04-15",
          preset: "custom",
        }}
        onChange={onChange}
      />,
    );
    onChange.mockClear();
    const from = getByLabelText("Data inicial") as HTMLInputElement;
    fireEvent.change(from, { target: { value: "2026-04-20" } });

    expect(getByRole("alert")).toHaveTextContent(/anterior ou igual/i);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("respeita hidePresets", () => {
    const { queryByText } = render(
      <PeriodPicker today={TODAY} hidePresets />,
    );
    expect(queryByText("Mes atual")).toBeNull();
  });
});
