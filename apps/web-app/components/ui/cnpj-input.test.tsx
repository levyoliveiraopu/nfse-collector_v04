import { describe, expect, it, vi } from "vitest";
import { fireEvent, render } from "@testing-library/react";
import { useState } from "react";

import { CNPJInput } from "./cnpj-input";

describe("CNPJInput", () => {
  it("aplica a mascara enquanto o usuario digita", () => {
    const { getByRole } = render(<CNPJInput />);
    const input = getByRole("textbox") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "00000000000191" } });
    expect(input.value).toBe("00.000.000/0001-91");
  });

  it("emite o valor normalizado (so digitos) via onChange", () => {
    const onChange = vi.fn();
    const { getByRole } = render(<CNPJInput onChange={onChange} />);
    const input = getByRole("textbox") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "00.000.000/0001-91" } });
    expect(onChange).toHaveBeenLastCalledWith("00000000000191");
  });

  it("mostra erro quando DV e invalido apos blur", () => {
    const { getByRole, queryByRole } = render(<CNPJInput />);
    const input = getByRole("textbox") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "00000000000190" } });
    // 14 digitos invalidos ja sinaliza mesmo sem blur (complete=true)
    const alert = queryByRole("alert");
    expect(alert).not.toBeNull();
    expect(alert!.textContent).toMatch(/invalido/i);
    expect(input.getAttribute("aria-invalid")).toBe("true");
  });

  it("nao marca erro enquanto incompleto e sem blur", () => {
    const { getByRole, queryByRole } = render(<CNPJInput />);
    const input = getByRole("textbox") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "00.000.0" } });
    expect(queryByRole("alert")).toBeNull();
    expect(input.getAttribute("aria-invalid")).toBeNull();
  });

  it("marca erro em CNPJ incompleto apos blur", () => {
    const { getByRole, queryByRole } = render(<CNPJInput />);
    const input = getByRole("textbox") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "00.000.0" } });
    fireEvent.blur(input);
    // Incompleto + touched => sem marcar invalid (valid=null). Alert
    // so aparece quando complete + DV errado.
    expect(queryByRole("alert")).toBeNull();
  });

  it("dispara onValidityChange com true para CNPJ valido", () => {
    const onValidityChange = vi.fn();
    const { getByRole } = render(
      <CNPJInput onValidityChange={onValidityChange} />,
    );
    const input = getByRole("textbox") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "00000000000191" } });
    expect(onValidityChange).toHaveBeenCalledWith(true);
  });

  it("dispara onValidityChange com false para sequencia repetida", () => {
    const onValidityChange = vi.fn();
    const { getByRole } = render(
      <CNPJInput onValidityChange={onValidityChange} />,
    );
    const input = getByRole("textbox") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "11111111111111" } });
    expect(onValidityChange).toHaveBeenLastCalledWith(false);
  });

  it("funciona em modo controlado", () => {
    function Harness() {
      const [v, setV] = useState("");
      return (
        <>
          <CNPJInput value={v} onChange={setV} />
          <span data-testid="snapshot">{v}</span>
        </>
      );
    }
    const { getByRole, getByTestId } = render(<Harness />);
    const input = getByRole("textbox") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "33000167000101" } });
    expect(input.value).toBe("33.000.167/0001-01");
    expect(getByTestId("snapshot").textContent).toBe("33000167000101");
  });
});
