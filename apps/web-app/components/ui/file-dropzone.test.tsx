import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, waitFor } from "@testing-library/react";

import { FileDropzone, acceptsFile } from "./file-dropzone";

function makeFile(
  name: string,
  { size = 1024, type = "" }: { size?: number; type?: string } = {},
): File {
  const file = new File(["x".repeat(Math.min(size, 1024))], name, { type });
  // Override size para simular arquivos grandes sem alocar memoria.
  Object.defineProperty(file, "size", { value: size });
  return file;
}

describe("acceptsFile", () => {
  it("aceita por extensao", () => {
    expect(acceptsFile(makeFile("cert.pfx"), ".pfx,.p12")).toBe(true);
    expect(acceptsFile(makeFile("cert.p12"), ".pfx,.p12")).toBe(true);
  });

  it("rejeita quando extensao nao bate", () => {
    expect(acceptsFile(makeFile("cert.txt"), ".pfx,.p12")).toBe(false);
  });

  it("aceita por MIME exato", () => {
    expect(
      acceptsFile(
        makeFile("cert", { type: "application/x-pkcs12" }),
        "application/x-pkcs12",
      ),
    ).toBe(true);
  });

  it("aceita wildcard MIME", () => {
    expect(
      acceptsFile(makeFile("a.png", { type: "image/png" }), "image/*"),
    ).toBe(true);
  });

  it("aceita qualquer arquivo sem accept", () => {
    expect(acceptsFile(makeFile("x.anything"), undefined)).toBe(true);
  });
});

describe("FileDropzone", () => {
  it("chama onUpload ao receber drop valido", async () => {
    const onUpload = vi.fn().mockResolvedValue(undefined);
    const { getByRole } = render(
      <FileDropzone accept=".pfx" maxSize={1024 * 1024} onUpload={onUpload} />,
    );
    const zone = getByRole("button");
    const file = makeFile("cert.pfx", { size: 2048 });

    fireEvent.drop(zone, {
      dataTransfer: { files: [file] },
    });

    await waitFor(() => expect(onUpload).toHaveBeenCalledWith(file));
    await waitFor(() =>
      expect(zone.getAttribute("data-status")).toBe("success"),
    );
  });

  it("rejeita arquivo acima do maxSize sem chamar onUpload", () => {
    const onUpload = vi.fn();
    const { getByRole, getByText } = render(
      <FileDropzone
        accept=".pfx"
        maxSize={1024}
        onUpload={onUpload}
      />,
    );
    const zone = getByRole("button");
    const file = makeFile("huge.pfx", { size: 2048 });

    fireEvent.drop(zone, { dataTransfer: { files: [file] } });

    expect(onUpload).not.toHaveBeenCalled();
    expect(zone.getAttribute("data-status")).toBe("error");
    expect(getByText(/excede o limite/i)).toBeInTheDocument();
  });

  it("rejeita tipo nao suportado", () => {
    const onUpload = vi.fn();
    const { getByRole, getByText } = render(
      <FileDropzone accept=".pfx" onUpload={onUpload} />,
    );
    const zone = getByRole("button");
    const file = makeFile("note.txt");

    fireEvent.drop(zone, { dataTransfer: { files: [file] } });

    expect(onUpload).not.toHaveBeenCalled();
    expect(zone.getAttribute("data-status")).toBe("error");
    expect(getByText(/tipo nao suportado/i)).toBeInTheDocument();
  });

  it("mantem status error quando onUpload rejeita", async () => {
    const onUpload = vi.fn().mockRejectedValue(new Error("API caiu"));
    const { getByRole, findByText } = render(
      <FileDropzone accept=".pfx" onUpload={onUpload} />,
    );
    const zone = getByRole("button");
    const file = makeFile("cert.pfx", { size: 100 });

    fireEvent.drop(zone, { dataTransfer: { files: [file] } });

    await waitFor(() => expect(onUpload).toHaveBeenCalled());
    await findByText(/api caiu/i);
    expect(zone.getAttribute("data-status")).toBe("error");
  });
});
