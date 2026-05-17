/**
 * Tests E2E — Dashboard del panel admin.
 * Verifica: métricas, nombre del operador, redirección sin auth.
 */

import { test, expect } from "@playwright/test";
import { API, MOCK_METRICS, MOCK_OPERATOR, setLoggedIn, mockAllRoutes } from "./helpers";

test.describe("Dashboard — autenticación", () => {
  test("sin token redirige al login", async ({ page }) => {
    // Sin setLoggedIn — sin token en localStorage
    await page.goto("/dashboard.html");
    await expect(page).toHaveURL(/index\.html/, { timeout: 5000 });
  });
});

test.describe("Dashboard — métricas", () => {
  test.beforeEach(async ({ page }) => {
    await setLoggedIn(page);
    await mockAllRoutes(page);
    await page.goto("/dashboard.html");
    // Esperar a que el valor se llene (no solo que el elemento exista con "—")
    await page.waitForFunction(
      () => {
        const el = document.getElementById("float-total");
        return el && el.textContent !== "—" && el.textContent !== "";
      },
      { timeout: 8000 }
    );
  });

  test("muestra el float total", async ({ page }) => {
    await expect(page.locator("#float-total")).toHaveText("$12345.67");
  });

  test("muestra el float fiat", async ({ page }) => {
    await expect(page.locator("#float-fiat")).toHaveText("$10000.00");
  });

  test("muestra el total de usuarios", async ({ page }) => {
    await expect(page.locator("#users-total")).toHaveText("238");
  });

  test("muestra usuarios nuevos hoy", async ({ page }) => {
    await expect(page.locator("#users-today")).toContainText("+5");
  });

  test("muestra depósitos pendientes", async ({ page }) => {
    await expect(page.locator("#dep-pending")).toHaveText("3");
  });

  test("muestra retiros pendientes", async ({ page }) => {
    await expect(page.locator("#wd-pending")).toHaveText("1");
  });

  test("muestra fees de hoy", async ({ page }) => {
    await expect(page.locator("#fees-today")).toHaveText("$45.50");
  });

  test("muestra fees del mes", async ({ page }) => {
    await expect(page.locator("#fees-month")).toHaveText("$1280.00");
  });

  test("muestra volumen de hoy", async ({ page }) => {
    await expect(page.locator("#volume-today")).toHaveText("$8900.00");
  });
});

test.describe("Dashboard — operador", () => {
  test("muestra el nombre del operador autenticado", async ({ page }) => {
    await setLoggedIn(page);
    await mockAllRoutes(page);
    await page.goto("/dashboard.html");
    await expect(page.locator("#operator-name")).toHaveText(
      MOCK_OPERATOR.name,
      { timeout: 5000 }
    );
  });
});

test.describe("Dashboard — alerta de pendientes", () => {
  test("muestra alerta cuando hay depósitos o retiros pendientes", async ({ page }) => {
    await setLoggedIn(page);
    await mockAllRoutes(page); // MOCK_METRICS tiene deposits_pending:3, withdrawals_pending:1
    await page.goto("/dashboard.html");

    // Esperar a que carguen las métricas
    await page.waitForFunction(
      () => {
        const el = document.getElementById("float-total");
        return el && el.textContent !== "—" && el.textContent !== "";
      },
      { timeout: 8000 }
    );

    const alert = page.locator("#pending-alert");
    await expect(alert).toBeVisible({ timeout: 3000 });
    await expect(alert).toContainText("3");
    await expect(alert).toContainText("1");
  });

  test("oculta la alerta cuando no hay pendientes", async ({ page }) => {
    await setLoggedIn(page);
    await mockAllRoutes(page);

    // Override con 0 pendientes (registrar ANTES del goto para que tenga prioridad)
    await page.route(`${API}/admin/dashboard`, route =>
      route.fulfill({ json: { ...MOCK_METRICS, deposits_pending: 0, withdrawals_pending: 0 } })
    );

    await page.goto("/dashboard.html");
    await page.waitForFunction(
      () => {
        const el = document.getElementById("float-total");
        return el && el.textContent !== "—" && el.textContent !== "";
      },
      { timeout: 8000 }
    );

    const alert = page.locator("#pending-alert");
    const classes = await alert.getAttribute("class");
    expect(classes).toContain("hidden");
  });
});

test.describe("Dashboard — navegación", () => {
  test.beforeEach(async ({ page }) => {
    await setLoggedIn(page);
    await mockAllRoutes(page);
    await page.goto("/dashboard.html");
    await page.waitForFunction(
      () => {
        const el = document.getElementById("float-total");
        return el && el.textContent !== "—" && el.textContent !== "";
      },
      { timeout: 8000 }
    );
  });

  test("tiene enlace a depósitos en la nav", async ({ page }) => {
    const link = page.locator('.nav a[href="deposits.html"]');
    await expect(link).toBeVisible();
  });

  test("tiene enlace a retiros en la nav", async ({ page }) => {
    const link = page.locator('.nav a[href="withdrawals.html"]');
    await expect(link).toBeVisible();
  });

  test("tiene enlace a usuarios en la nav", async ({ page }) => {
    const link = page.locator('.nav a[href="users.html"]');
    await expect(link).toBeVisible();
  });

  test("tiene enlace a historial en la nav", async ({ page }) => {
    const link = page.locator('.nav a[href="history.html"]');
    await expect(link).toBeVisible();
  });

  test("tiene botón de tema claro/oscuro", async ({ page }) => {
    await expect(page.locator("#theme-btn")).toBeVisible();
  });

  test("botón de tema cambia el modo", async ({ page }) => {
    const btn = page.locator("#theme-btn");
    const initialText = await btn.textContent();
    await btn.click();
    const newText = await btn.textContent();
    expect(newText).not.toBe(initialText);
  });
});
