/**
 * Tests E2E — Página de depósitos pendientes.
 * Verifica: listado, datos del depósito, aprobar, rechazar.
 */

import { test, expect } from "@playwright/test";
import { API, MOCK_DEPOSIT, setLoggedIn, mockAllRoutes } from "./helpers";

test.beforeEach(async ({ page }) => {
  await setLoggedIn(page);
  await mockAllRoutes(page);
});

test.describe("Depósitos — listado", () => {
  test("muestra el depósito pendiente", async ({ page }) => {
    await page.goto("/deposits.html");
    await expect(page.locator(".card").first()).toBeVisible({ timeout: 5000 });
  });

  test("muestra el nombre del usuario", async ({ page }) => {
    await page.goto("/deposits.html");
    await expect(page.getByText("Stanley Bolivar Llaguno Caicedo")).toBeVisible();
  });

  test("muestra la cédula del usuario", async ({ page }) => {
    await page.goto("/deposits.html");
    await expect(page.getByText("0928732494")).toBeVisible();
  });

  test("muestra el monto del depósito", async ({ page }) => {
    await page.goto("/deposits.html");
    await expect(page.getByText("$150.00")).toBeVisible();
  });

  test("muestra el banco", async ({ page }) => {
    await page.goto("/deposits.html");
    await expect(page.getByText("Banco Pichincha")).toBeVisible();
  });

  test("muestra el número de referencia", async ({ page }) => {
    await page.goto("/deposits.html");
    await expect(page.getByText("REF-2024-001")).toBeVisible();
  });

  test("muestra el badge Pendiente", async ({ page }) => {
    await page.goto("/deposits.html");
    await expect(page.locator(".badge-pending").first()).toBeVisible();
  });

  test("muestra botón de aprobar", async ({ page }) => {
    await page.goto("/deposits.html");
    await expect(page.locator(".btn-approve").first()).toBeVisible();
    await expect(page.locator(".btn-approve").first()).toContainText("Aprobar");
  });

  test("muestra botón de rechazar", async ({ page }) => {
    await page.goto("/deposits.html");
    await expect(page.locator(".btn-reject").first()).toBeVisible();
    await expect(page.locator(".btn-reject").first()).toContainText("Rechazar");
  });
});

test.describe("Depósitos — sin pendientes", () => {
  test("muestra mensaje vacío cuando no hay depósitos", async ({ page }) => {
    await page.route(`${API}/admin/deposits/pending`, route =>
      route.fulfill({ json: [] })
    );
    await page.goto("/deposits.html");
    await expect(page.locator(".empty")).toBeVisible({ timeout: 3000 });
    await expect(page.locator(".empty")).toContainText("pendientes");
  });
});

test.describe("Depósitos — aprobar", () => {
  test("aprobar un depósito llama al endpoint correcto", async ({ page }) => {
    let approveUrl = "";
    await page.route(`${API}/admin/deposits/*/approve`, route => {
      approveUrl = route.request().url();
      return route.fulfill({ json: { ok: true } });
    });

    await page.goto("/deposits.html");
    await page.waitForSelector(".btn-approve");

    // Registrar handler ANTES del click
    page.once("dialog", dialog => dialog.accept());
    await page.locator(".btn-approve").first().click();

    await page.waitForTimeout(500);
    expect(approveUrl).toContain("/admin/deposits/");
    expect(approveUrl).toContain("/approve");
  });

  test("aprobar muestra toast de éxito", async ({ page }) => {
    await page.goto("/deposits.html");
    await page.waitForSelector(".btn-approve");

    page.once("dialog", dialog => dialog.accept());
    await page.locator(".btn-approve").first().click();

    await expect(page.locator(".toast")).toBeVisible({ timeout: 3000 });
    await expect(page.locator(".toast")).toContainText("aprobado");
  });
});

test.describe("Depósitos — rechazar", () => {
  test("rechazar abre prompt de motivo", async ({ page }) => {
    await page.goto("/deposits.html");

    let dialogAppeared = false;
    page.once("dialog", dialog => {
      dialogAppeared = true;
      dialog.dismiss();
    });

    await page.locator(".btn-reject").first().click();
    await page.waitForTimeout(300);
    expect(dialogAppeared).toBe(true);
  });

  test("cancelar el prompt NO rechaza el depósito", async ({ page }) => {
    let rejectCalled = false;
    await page.route(`${API}/admin/deposits/*/reject`, route => {
      rejectCalled = true;
      return route.fulfill({ json: { ok: true } });
    });

    await page.goto("/deposits.html");

    page.once("dialog", dialog => dialog.dismiss()); // cancelar
    await page.locator(".btn-reject").first().click();
    await page.waitForTimeout(500);

    expect(rejectCalled).toBe(false);
  });
});
