import * as React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { ErrorBoundary } from "./error-boundary";

function Bomb({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error("boom");
  return <p>conteudo ok</p>;
}

describe("ErrorBoundary", () => {
  let errorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    errorSpy.mockRestore();
  });

  it("renderiza filhos quando nao ha erro", () => {
    render(
      <ErrorBoundary>
        <Bomb shouldThrow={false} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("conteudo ok")).toBeInTheDocument();
  });

  it("mostra fallback default quando filho lanca", () => {
    render(
      <ErrorBoundary>
        <Bomb shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("boom")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Tentar novamente" }),
    ).toBeInTheDocument();
  });

  it("onRetry + reset re-renderizam o filho quando o throw para", () => {
    const onRetry = vi.fn();

    function Harness() {
      const [shouldThrow, setShouldThrow] = React.useState(true);
      return (
        <ErrorBoundary
          onRetry={() => {
            onRetry();
            setShouldThrow(false);
          }}
        >
          <Bomb shouldThrow={shouldThrow} />
        </ErrorBoundary>
      );
    }

    render(<Harness />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
    expect(screen.getByText("conteudo ok")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("aceita fallback custom via funcao com acesso a error/reset", () => {
    render(
      <ErrorBoundary
        fallback={({ error, reset }) => (
          <div>
            <span>custom: {error.message}</span>
            <button onClick={reset}>reset custom</button>
          </div>
        )}
      >
        <Bomb shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("custom: boom")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "reset custom" }),
    ).toBeInTheDocument();
  });

  it("onError recebe o erro capturado", () => {
    const onError = vi.fn();
    render(
      <ErrorBoundary onError={onError}>
        <Bomb shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0][0]).toBeInstanceOf(Error);
    expect(onError.mock.calls[0][0].message).toBe("boom");
  });
});
