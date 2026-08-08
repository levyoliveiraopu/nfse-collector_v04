import { describe, expect, it } from "vitest";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";

import {
  HELP_CATALOG,
  HELP_FALLBACK,
  normalizeSearchText,
  resolveHelpEntry,
} from "./catalog";

describe("help catalog", () => {
  it.each([
    ["/dashboard", "dashboard"],
    ["/empresas", "companies"],
    ["/empresas/abc", "company-detail"],
    ["/dashboard/empresas/abc/credencial", "credential"],
    ["/execucoes", "executions"],
    ["/execucoes/nova", "execution-new"],
    ["/execucoes/123", "execution-detail"],
    ["/agendamentos", "schedules"],
    ["/ocorrencias", "occurrences"],
    ["/ocorrencias/123", "occurrence-detail"],
    ["/arquivos", "files"],
    ["/usuarios", "users"],
    ["/dashboard/assinatura", "subscription"],
    ["/ajuda", "help-overview"],
    ["/login", "access-login"],
    ["/redefinir-senha/token", "access-reset"],
  ])("resolves %s to %s", (pathname, slug) => {
    expect(resolveHelpEntry(pathname, "operator").slug).toBe(slug);
  });

  it("falls back without exposing a dynamic route", () => {
    expect(resolveHelpEntry("/rota/desconhecida/uuid", "viewer")).toBe(
      HELP_FALLBACK,
    );
  });

  it("normalizes accents and case for local search", () => {
    expect(normalizeSearchText("  Execuções e Certificação  ")).toBe(
      "execucoes e certificacao",
    );
  });

  it("keeps slugs unique and every tour read-only", () => {
    expect(new Set(HELP_CATALOG.map((entry) => entry.slug)).size).toBe(
      HELP_CATALOG.length,
    );
    for (const entry of HELP_CATALOG) {
      for (const step of entry.tourSteps ?? []) {
        expect(step.target).toMatch(/^\[data-help-id=/);
      }
    }
  });

  it("has one sanitized markdown file for every catalog entry", () => {
    const helpDir = path.resolve(process.cwd(), "public/help");
    const files = readdirSync(helpDir)
      .filter((name) => name.endsWith(".md"))
      .map((name) => name.replace(/\.md$/, ""))
      .sort();
    const slugs = HELP_CATALOG.map((entry) => entry.slug).sort();
    expect(files).toEqual(slugs);

    for (const slug of slugs) {
      const content = readFileSync(path.join(helpDir, `${slug}.md`), "utf8");
      expect(content).not.toMatch(
        /<script|BEGIN (RSA )?PRIVATE KEY|X-Amz-Signature|demo12345|admin@demo\.local/i,
      );
      expect(content).not.toMatch(/<[^>]+>/);
    }
  });

  it("maps every functional page and keeps explicit exclusions", () => {
    const appDir = path.resolve(process.cwd(), "app");
    const pages: string[] = [];

    function walk(directory: string) {
      for (const item of readdirSync(directory, { withFileTypes: true })) {
        const absolute = path.join(directory, item.name);
        if (item.isDirectory()) walk(absolute);
        if (item.isFile() && item.name === "page.tsx") pages.push(absolute);
      }
    }
    walk(appDir);

    const excluded = new Set([
      "/",
      "/legal",
      "/styleguide",
      // Compatibilidade com favoritos antigos: estas paginas apenas
      // redirecionam e nunca renderizam ajuda propria.
      "/dashboard/notas",
      "/dashboard/certificados",
    ]);
    const routes = pages.map((file) => {
      const relative = path.relative(appDir, path.dirname(file));
      const segments = relative
        .split(path.sep)
        .filter((segment) => segment && !/^\(.+\)$/.test(segment))
        .map((segment) =>
          /^\[.+\]$/.test(segment) ? `sample-${segment.slice(1, -1)}` : segment,
        );
      return `/${segments.join("/")}`.replace(/\/$/, "") || "/";
    });

    for (const route of routes.filter((candidate) => !excluded.has(candidate))) {
      const entry = resolveHelpEntry(route, "owner");
      if (route === "/ajuda") {
        expect(entry.slug).toBe("help-overview");
      } else {
        expect(entry, `rota sem ajuda: ${route}`).not.toBe(HELP_FALLBACK);
      }
    }
  });

  it("keeps every tour selector backed by a stable source attribute", () => {
    const roots = [
      path.resolve(process.cwd(), "app"),
      path.resolve(process.cwd(), "components"),
    ];
    let source = "";
    function collect(directory: string) {
      for (const item of readdirSync(directory, { withFileTypes: true })) {
        const absolute = path.join(directory, item.name);
        if (item.isDirectory()) collect(absolute);
        if (item.isFile() && item.name.endsWith(".tsx")) {
          source += readFileSync(absolute, "utf8");
        }
      }
    }
    roots.filter(existsSync).forEach(collect);

    for (const entry of HELP_CATALOG) {
      for (const step of entry.tourSteps ?? []) {
        const id = step.target.match(/data-help-id="([^"]+)"/)?.[1];
        expect(id, `seletor invalido em ${entry.slug}`).toBeTruthy();
        expect(source, `seletor ausente: ${id}`).toContain(
          `data-help-id="${id}"`,
        );
      }
    }
  });
});
