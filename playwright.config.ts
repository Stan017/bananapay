import { defineConfig, devices } from "@playwright/test";
import path from "path";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  retries: 0,
  reporter: "list",
  timeout: 15_000,

  use: {
    // Sirve el panel como archivos estáticos locales
    baseURL: "http://localhost:9876",
    headless: true,
    screenshot: "only-on-failure",
  },

  // Levanta un servidor HTTP estático apuntando a /panel antes de los tests
  webServer: {
    command: "npx http-server panel -p 9876 --cors -s",
    url: "http://localhost:9876",
    reuseExistingServer: true,
    timeout: 10_000,
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
