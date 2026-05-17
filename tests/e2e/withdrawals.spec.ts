/**
 * Tests E2E — Página de retiros pendientes.
 * Verifica: listado, datos bancarios, aprobar, rechazar.
 */

import { test, expect } from "@playwright/test";
import { API, MOCK_WITHDRAWAL, setLoggedIn, mockAllRoutes } from "./helpers";

test.beforeEach(async ({ page }) => {
  await setLoggedIn(page);
  await mockAllRoutes(page);
});

test.describe("Retiros — listado", () => {
  test("muestra el retiro pendiente", async ({ page }) => {
    await page.goto("/withdrawals.html");
    await expect(page.locator(".card").first()).toBeVisible({ timeout: 5000 });
  });

  test("muestra el nombre del usuario", async ({ page }) => {
    await page.goto("/withdrawals.html");
    await expect(page.getByText("Stanley Bolivar Llaguno Caicedo")).toBeVisible();
  });

  test("muestra el monto del retiro", async ({ page }) => {
    await page.goto("/withdrawals.html");
    await expect(page.getByText("$200.00")).toBeVisible();
  });

  test("muestra el monto que recibe el usuario", async ({ page }) => {
    await page.goto("/withdrawals.html");
    await expect(page.getByText("$197.00")).toBeVisible();
  });

  test("muestra el banco destino", async ({ page }) => {
    await page.goto("/withdrawals.html");
    await expect(page.getByText("Banco Guayaquil")).toBeVisible();
  });

  test("muestra el número de cuenta", async ({ page }) => {
    await page.goto("/withdrawals.html");
    await expect(page.getByText("1234567890")).toBeVisible();
  });

  test("muestra el tipo de retiro instant", async ({ page }) => {
    await page.goto("/withdrawals.html");
    await expect(page.getByText(/instant/i).first()).toBeVisible();
  });

  test("muestra el fee del retiro", async ({ page }) => {
    await page.goto("/withdrawals.html");
    await expect(page.getByText("$3.00")).toBeVisible();
  });

  test("muestra botón Transferí", async ({ page }) => {
    await page.goto("/withdrawals.html");
    await expect(page.locator(".btn-approve").first()).toContainText("Transferí");
  });

  test("muestra botón Rechazar", async ({ page }) => {
    await page.goto("/withdrawals.html");
    await expect(page.locator(".btn-reject").first()).toContainText("Rechazar");
  });

  test("muestra badge Pendiente", async ({ page }) => {
    await page.goto("/withdrawals.html");
    await expect(page.locator(".badge-pending").first()).toBeVisible();
  });
});

test.describe("Retiros — sin pendientes", () => {
  test("muestra mensaje vacío cuando no hay retiros", async ({ page }) => {
    await page.route(`${API}/admin/withdrawals/pending`, route =>
      route.fulfill({ json: [] })
    );
    await page.goto("/withdrawals.html");
    await expect(page.locator(".empty")).toBeVisible({ timeout: 3000 });
    await expect(page.locator(".empty")).toContainText("pendientes");
  });
});

test.describe("Retiros — aprobar", () => {
  test("aprobar llama el endpoint correcto", async ({ page }) => {
    let approveUrl = "";
    await page.route(`${API}/admin/withdrawals/*/approve`, route => {
      approveUrl = route.request().url();
      return route.fulfill({ json: { ok: true } });
    });

    await page.goto("/withdrawals.html");
    await page.waitForSelector(".btn-approve");

    page.once("dialog", dialog => dialog.accept());
    await page.locator(".btn-approve").first().click();

    await page.waitForTimeout(500);
    expect(approveUrl).toContain("/admin/withdrawals/");
    expect(approveUrl).toContain("/approve");
  });

  test("aprobar muestra toast de confirmación", async ({ page }) => {
    await page.goto("/withdrawals.html");
    await page.waitForSelector(".btn-approve");

    page.once("dialog", dialog => dialog.accept());
    await page.locator(".btn-approve").first().click();

    await expect(page.locator(".toast")).toBeVisible({ timeout: 3000 });
    await expect(page.locator(".toast")).toContainText("aprobado");
  });

  test("aprobar elimina la tarjeta del DOM", async ({ page }) => {
    await page.goto("/withdrawals.html");
    await page.waitForSelector(".card");
    const cardId = `wd-${MOCK_WITHDRAWAL.id}`;

    page.once("dialog", dialog => dialog.accept());
    await page.locator(".btn-approve").first().click();

    await expect(page.locator(`#${cardId}`)).not.toBeVisible({ timeout: 3000 });
  });
});

test.describe("Retiros — rechazar", () => {
  test("rechazar abre prompt de motivo", async ({ page }) => {
    await page.goto("/withdrawals.html");

    let dialogType = "";
    page.once("dialog", dialog => {
      dialogType = dialog.type();
      dialog.dismiss();
    });

    await page.locator(".btn-reject").first().click();
    await page.waitForTimeout(300);
    expect(dialogType).toBe("prompt");
  });
});
