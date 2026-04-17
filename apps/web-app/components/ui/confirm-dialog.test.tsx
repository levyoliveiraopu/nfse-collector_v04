import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { ConfirmDialog } from "./confirm-dialog";

describe("ConfirmDialog", () => {
  it("nao renderiza quando open=false", () => {
    render(
      <ConfirmDialog
        open={false}
        onClose={() => {}}
        onConfirm={() => {}}
        title="Excluir"
      />,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("sem confirmPhrase: Confirmar habilitado de cara", () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        open
        onClose={() => {}}
        onConfirm={onConfirm}
        title="Confirmar acao"
      />,
    );
    const confirm = screen.getByRole("button", { name: "Confirmar" });
    expect(confirm).not.toBeDisabled();
    fireEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("com confirmPhrase: bloqueia Confirmar ate digitar match exato", () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        open
        onClose={() => {}}
        onConfirm={onConfirm}
        title="Excluir empresa ACME"
        description="Acao irreversivel"
        confirmPhrase="ACME"
        tone="destructive"
        confirmLabel="Excluir"
      />,
    );
    const confirm = screen.getByRole("button", { name: "Excluir" });
    expect(confirm).toBeDisabled();

    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "acme" } });
    expect(confirm).toBeDisabled();

    fireEvent.change(input, { target: { value: "ACME2" } });
    expect(confirm).toBeDisabled();

    fireEvent.change(input, { target: { value: "ACME" } });
    expect(confirm).not.toBeDisabled();

    fireEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("aceita match com espacos ao redor (trim)", () => {
    render(
      <ConfirmDialog
        open
        onClose={() => {}}
        onConfirm={() => {}}
        title="Remover"
        confirmPhrase="DELETE"
      />,
    );
    const confirm = screen.getByRole("button", { name: "Confirmar" });
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "  DELETE  " },
    });
    expect(confirm).not.toBeDisabled();
  });

  it("tone=destructive aplica classe destrutiva no botao confirmar", () => {
    render(
      <ConfirmDialog
        open
        onClose={() => {}}
        onConfirm={() => {}}
        title="Excluir"
        tone="destructive"
      />,
    );
    const confirm = screen.getByRole("button", { name: "Confirmar" });
    expect(confirm).toHaveAttribute("data-tone", "destructive");
    expect(confirm.className).toMatch(/bg-destructive/);
  });

  it("Cancelar dispara onClose", () => {
    const onClose = vi.fn();
    render(
      <ConfirmDialog
        open
        onClose={onClose}
        onConfirm={() => {}}
        title="Acao"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("busy desabilita Confirmar mesmo com match", () => {
    render(
      <ConfirmDialog
        open
        onClose={() => {}}
        onConfirm={() => {}}
        title="Excluir"
        confirmPhrase="GO"
        busy
      />,
    );
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "GO" } });
    expect(screen.getByRole("button", { name: "Confirmar" })).toBeDisabled();
  });
});
