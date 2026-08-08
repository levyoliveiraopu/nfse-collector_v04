import { beforeEach, describe, expect, it, vi } from "vitest";
import { redirect } from "next/navigation";
import LegacyCertificadosPage from "./certificados/page";
import LegacyNotasPage from "./notas/page";
import { NAV_ITEMS } from "@/components/app-shell/nav-items";

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}));

describe("rotas legadas do dashboard", () => {
  beforeEach(() => {
    vi.mocked(redirect).mockClear();
  });

  it("encaminha Notas para a area funcional de Arquivos", () => {
    LegacyNotasPage();

    expect(redirect).toHaveBeenCalledOnce();
    expect(redirect).toHaveBeenCalledWith("/arquivos");
  });

  it("encaminha Certificados para a area funcional de Empresas", () => {
    LegacyCertificadosPage();

    expect(redirect).toHaveBeenCalledOnce();
    expect(redirect).toHaveBeenCalledWith("/empresas");
  });

  it("nao exibe placeholders sem pagina no menu", () => {
    expect(NAV_ITEMS.map((item) => item.label)).not.toEqual(
      expect.arrayContaining([
        "Notas",
        "Certificados",
        "Tenants",
        "Configuracoes",
      ]),
    );
  });
});
