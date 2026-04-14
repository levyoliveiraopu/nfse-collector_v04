import { test, expect, type Route } from "@playwright/test";

/**
 * E2E de autenticacao (APP-01).
 *
 * As specs interceptam `/api/auth/*` (Route Handlers do Next) via
 * `page.route` para nao dependerem de Postgres/FastAPI em CI. O que
 * validamos aqui:
 *
 * 1. Signup valido redireciona para `/dashboard` e renderiza o shell.
 * 2. Access token expira -> AuthProvider chama `/api/auth/refresh` e
 *    rehidrata a sessao automaticamente (refresh automatico).
 */

type AuthSessionStub = {
  access_token: string;
  expires_in: number;
  user: { userId: string; tenantId: string; role: string };
};

function buildSession(overrides: Partial<AuthSessionStub> = {}): AuthSessionStub {
  return {
    access_token: "access-token-stub",
    expires_in: 60,
    user: {
      userId: "00000000-0000-0000-0000-000000000001",
      tenantId: "00000000-0000-0000-0000-000000000002",
      role: "owner",
      ...overrides.user,
    },
    ...overrides,
  };
}

async function fulfillJson(route: Route, status: number, body: unknown) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

test.describe("fluxo de auth", () => {
  test("signup -> dashboard", async ({ page }) => {
    await page.route("**/api/auth/refresh", async (route) => {
      await fulfillJson(route, 401, { detail: "sessao expirada" });
    });
    await page.route("**/api/auth/signup", async (route) => {
      const request = route.request();
      expect(request.method()).toBe("POST");
      const payload = JSON.parse(request.postData() ?? "{}");
      expect(payload).toMatchObject({
        tenant_name: "Acme Contabil",
        tenant_slug: "acme-contabil",
        name: "Fulano",
        email: "fulano@acme.com",
      });
      await fulfillJson(route, 201, buildSession({ expires_in: 900 }));
    });

    await page.goto("/signup");
    await page.getByLabel("Nome da empresa").fill("Acme Contabil");
    await page.getByLabel("Identificador (slug)").fill("acme-contabil");
    await page.getByLabel("Seu nome").fill("Fulano");
    await page.getByLabel("Email").fill("fulano@acme.com");
    await page.getByLabel("Senha").fill("senha-forte-123");
    await page.getByLabel(/Li e aceito os/).check();
    await page.getByRole("button", { name: "Criar conta" }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(
      page.getByRole("heading", { name: "Dashboard" }),
    ).toBeVisible();
  });

  test("refresh automatico rehidrata a sessao", async ({ page }) => {
    // Primeiro bootstrap: refresh succeeda -> sessao autenticada.
    let refreshCalls = 0;
    await page.route("**/api/auth/refresh", async (route) => {
      refreshCalls += 1;
      await fulfillJson(
        route,
        200,
        buildSession({
          // expires_in baixo forca o timer a disparar novo refresh rapido.
          expires_in: 65,
          access_token: `access-${refreshCalls}`,
        }),
      );
    });

    await page.goto("/dashboard");
    await expect(
      page.getByRole("heading", { name: "Dashboard" }),
    ).toBeVisible();

    // O timer proativo esta em (expires_in - 60)s = 5s. Aguarda ate a
    // segunda chamada ao /api/auth/refresh sem interacao do usuario.
    await expect
      .poll(() => refreshCalls, { timeout: 15_000, intervals: [500] })
      .toBeGreaterThanOrEqual(2);
  });
});
