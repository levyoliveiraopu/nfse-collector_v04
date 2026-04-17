import { test, expect, type Route } from "@playwright/test";

/**
 * E2E do fluxo `/execucoes/nova` -> `/execucoes/[id]` com polling (APP-05).
 *
 * Intercepta via `page.route` tanto o `/api/auth/refresh` quanto os
 * endpoints da FastAPI (`/companies`, `/executions`, `/executions/{id}`,
 * `/executions/{id}/items`), para nao exigir Postgres/FastAPI no CI.
 *
 * Cobre o DoD: "cria, acompanha, ve itens aparecendo".
 */

function session() {
  return {
    access_token: "access-token-stub",
    expires_in: 900,
    user: {
      userId: "user-1",
      tenantId: "tenant-1",
      role: "operator" as const,
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

test.describe("fluxo /execucoes", () => {
  test("cria -> acompanha -> ve itens aparecendo (polling)", async ({ page }) => {
    await page.route("**/api/auth/refresh", (route) => json(route, 200, session()));

    // Listagem de companies para o multi-select.
    await page.route("**/companies?**", (route) =>
      json(route, 200, {
        items: [
          {
            id: "c1",
            tenant_id: "tenant-1",
            cnpj: "12345678000190",
            razao_social: "Acme Ltda",
            nome_fantasia: null,
            municipio_ibge: "3550308",
            uf: "SP",
            status: "active",
            last_nsu: 0,
            last_success_at: null,
            portal_provider: null,
            notes: null,
            created_at: "",
            updated_at: "",
          },
        ],
        page: 1,
        page_size: 100,
        total: 1,
      }),
    );

    // POST /executions -> 1 execucao criada com job_id.
    await page.route("**/executions", (route) => {
      if (route.request().method() === "POST") {
        return json(route, 201, {
          created: [
            {
              execution_id: "e1",
              company_id: "c1",
              status: "queued",
              job_id: "job-1",
              enqueue_error: null,
            },
          ],
        });
      }
      return route.continue();
    });

    // GET /executions/e1 -> primeiro running, depois succeeded.
    let detailCalls = 0;
    await page.route("**/executions/e1", (route) => {
      detailCalls += 1;
      const status = detailCalls === 1 ? "running" : "succeeded";
      const base = {
        id: "e1",
        tenant_id: "tenant-1",
        company_id: "c1",
        trigger: "manual",
        period_start: "2026-04-01",
        period_end: "2026-04-17",
        started_at: "2026-04-17T10:00:00Z",
        finished_at: status === "succeeded" ? "2026-04-17T10:00:05Z" : null,
        nsu_from: 0,
        nsu_to: status === "succeeded" ? 3 : null,
        error_summary: null,
        triggered_by_user_id: "user-1",
        created_at: "2026-04-17T10:00:00Z",
        updated_at: "2026-04-17T10:00:05Z",
      };
      return json(route, 200, {
        ...base,
        status,
        items_total: status === "succeeded" ? 3 : 1,
        items_ok: status === "succeeded" ? 3 : 1,
        items_fail: 0,
      });
    });

    // GET /executions/e1/items -> retorna items ao vivo.
    let itemsCalls = 0;
    await page.route("**/executions/e1/items?**", (route) => {
      itemsCalls += 1;
      const final = itemsCalls >= 2;
      return json(route, 200, {
        items: final
          ? [
              {
                id: "i1",
                tenant_id: "tenant-1",
                execution_id: "e1",
                nsu: 1,
                chave_nfse: "3525031412345000100550010000001111123456",
                cnpj_emitente: "12345678000190",
                data_emissao: "2026-04-15T12:00:00Z",
                valor: "100.00",
                xml_object_key: "tenants/tenant-1/executions/e1/1.xml",
                status: "ok",
                error_code: null,
                error_message: null,
                created_at: "",
                updated_at: "",
              },
              {
                id: "i2",
                tenant_id: "tenant-1",
                execution_id: "e1",
                nsu: 2,
                chave_nfse: "3525031412345000100550010000001112123457",
                cnpj_emitente: "12345678000190",
                data_emissao: "2026-04-15T12:00:00Z",
                valor: "250.50",
                xml_object_key: "tenants/tenant-1/executions/e1/2.xml",
                status: "ok",
                error_code: null,
                error_message: null,
                created_at: "",
                updated_at: "",
              },
            ]
          : [],
        page: 1,
        page_size: 50,
        total: final ? 2 : 0,
      });
    });

    // Lista global de execucoes (fallback quando redireciona pra /execucoes).
    await page.route("**/executions?**", (route) =>
      json(route, 200, { items: [], page: 1, page_size: 20, total: 0 }),
    );

    await page.goto("/execucoes/nova");

    await expect(
      page.getByRole("heading", { name: /Nova execucao/i }),
    ).toBeVisible();

    // Seleciona Acme Ltda.
    await page.getByRole("checkbox", { name: /Acme Ltda/i }).click();
    await page.getByRole("button", { name: /Iniciar/i }).click();

    // Chegou no detalhe.
    await expect(page).toHaveURL(/\/execucoes\/e1/);
    await expect(page.getByRole("progressbar")).toBeVisible();

    // Espera polling trazer items.
    await expect(page.locator('[data-item-id="i1"]')).toBeVisible({
      timeout: 8000,
    });
    await expect(page.locator('[data-item-id="i2"]')).toBeVisible();
  });
});
