import { test, expect, type Route } from "@playwright/test";

/**
 * E2E de gestao de usuarios + convites (APP-09).
 *
 * Intercepta via `page.route` tanto os Route Handlers do Next (`/api/auth/*`)
 * quanto os endpoints diretos da API FastAPI (`/tenant/*`), para nao exigir
 * Postgres/FastAPI no CI. Cobre:
 *
 *   1. Usuario logado abre `/usuarios`, envia convite e ve o item em
 *      "Convites pendentes".
 *   2. Aceite do convite em `/aceitar-convite/[token]` redireciona para
 *      `/dashboard`.
 *   3. Admin vendo owner na lista tem botao de acoes desabilitado.
 */

type SessionStub = {
  access_token: string;
  expires_in: number;
  user: { userId: string; tenantId: string; role: "owner" | "admin" };
};

function session(role: "owner" | "admin" = "owner"): SessionStub {
  return {
    access_token: "access-token-stub",
    expires_in: 900,
    user: {
      userId: "user-actor",
      tenantId: "tenant-1",
      role,
    },
  };
}

async function json(route: Route, status: number, body: unknown) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

test.describe("fluxo /usuarios", () => {
  test("owner convida novo membro e ve item em pendentes", async ({ page }) => {
    await page.route("**/api/auth/refresh", (route) => json(route, 200, session("owner")));
    await page.route("**/tenant/members", (route) =>
      json(route, 200, [
        {
          userId: "user-actor",
          email: "owner@tenant.com",
          name: "Dona do Tenant",
          role: "owner",
          status: "active",
          lastLoginAt: "2026-04-10T12:00:00Z",
          createdAt: "2026-01-01T00:00:00Z",
        },
      ]),
    );
    let inviteCalls = 0;
    await page.route("**/tenant/invitations", (route) => {
      if (route.request().method() === "POST") {
        inviteCalls += 1;
        const payload = JSON.parse(route.request().postData() ?? "{}");
        return json(route, 201, {
          id: "inv-new",
          email: payload.email,
          role: payload.role,
          status: "pending",
          createdAt: "2026-04-16T00:00:00Z",
          expiresAt: "2026-04-23T00:00:00Z",
          invitedByEmail: "owner@tenant.com",
        });
      }
      return json(route, 200, []);
    });

    await page.goto("/usuarios");
    await expect(
      page.getByRole("heading", { name: "Usuarios" }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: /convidar usuario/i })
      .first()
      .click();
    await page.getByLabel("Email").fill("novo@tenant.com");
    await page.getByLabel(/papel do usuario convidado/i).selectOption("operator");
    await page.getByRole("button", { name: /enviar convite/i }).click();

    await expect.poll(() => inviteCalls).toBe(1);
    await expect(page.getByText("novo@tenant.com")).toBeVisible();
  });

  test("aceitar convite redireciona para dashboard", async ({ page }) => {
    // refresh inicial: anonimo.
    await page.route("**/api/auth/refresh", (route) =>
      json(route, 401, { detail: "sessao expirada" }),
    );
    // Apos aceitar, o Route Handler grava refresh cookie e devolve session.
    await page.route("**/api/auth/accept-invitation", (route) => {
      const payload = JSON.parse(route.request().postData() ?? "{}");
      expect(payload.token).toBe("convite-token-123");
      return json(route, 200, {
        access_token: "access-novo",
        expires_in: 900,
        user: session("operator" as "admin").user,
      });
    });
    // /dashboard precisa dos membros da sessao depois que o refresh
    // automatico chama — devolvemos sessao autenticada a partir daqui.
    // Simples: o redirect usa router.replace e o AuthProvider ja aplicou
    // applySession do body de accept-invitation, entao nao precisa de novo
    // refresh.

    await page.goto("/aceitar-convite/convite-token-123");
    await page.getByLabel("Seu nome").fill("Novo Fulano");
    await page.getByLabel("Senha").fill("senha-forte-123");
    await page.getByLabel("Confirmar senha").fill("senha-forte-123");
    await page.getByRole("button", { name: /aceitar convite/i }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test("admin nao consegue agir sobre owner (botao desabilitado)", async ({
    page,
  }) => {
    await page.route("**/api/auth/refresh", (route) => json(route, 200, session("admin")));
    await page.route("**/tenant/members", (route) =>
      json(route, 200, [
        {
          userId: "owner-id",
          email: "owner@tenant.com",
          name: "Dona do Tenant",
          role: "owner",
          status: "active",
          lastLoginAt: null,
          createdAt: "2026-01-01T00:00:00Z",
        },
        {
          userId: "user-actor",
          email: "admin@tenant.com",
          name: "Admin Conectado",
          role: "admin",
          status: "active",
          lastLoginAt: "2026-04-14T00:00:00Z",
          createdAt: "2026-02-01T00:00:00Z",
        },
      ]),
    );
    await page.route("**/tenant/invitations", (route) => json(route, 200, []));

    await page.goto("/usuarios");
    const ownerActions = page.getByRole("button", {
      name: /acoes para dona do tenant/i,
    });
    await expect(ownerActions).toBeDisabled();
  });
});
