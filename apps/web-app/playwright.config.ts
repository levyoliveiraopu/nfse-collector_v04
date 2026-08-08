import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config do `apps/web-app`. Sobe o `next dev` numa porta dedicada
 * (3100) e intercepta chamadas a `/api/auth/*` via `page.route` em cada spec,
 * evitando dependencia de Postgres/FastAPI no CI. Ver APP-01.
 */
const PORT = Number(process.env.PLAYWRIGHT_PORT ?? 3100);
const useSystemChrome = process.env.PLAYWRIGHT_USE_SYSTEM_CHROME === "1";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: true,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        ...(useSystemChrome ? { channel: "chrome" } : {}),
      },
    },
  ],
  webServer: {
    command: `corepack pnpm exec next dev -p ${PORT}`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:65535",
      API_BASE_URL: "http://127.0.0.1:65535",
    },
  },
});
