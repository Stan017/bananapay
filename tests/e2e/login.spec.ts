/**
 * Tests E2E — Página de login del panel admin.
 * Verifica: renderizado, validación, login exitoso y fallido.
 */

import { test, expect } from "@playwright/test";
import { API, MOCK_TOKEN, MOCK_OPERATOR } from "./helpers";

test.describe("Login — renderizado", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/index.html");
  });

  test("muestra el título BananaPay Admin", async ({ page }) => {
    await expect(page.locator(".login-title")).toHaveText("BananaPay Admin");
  });

  test("muestra el emoji 🍌", async ({ page }) => {
    await expect(page.locator(".login-logo")).toHaveText("🍌");
  });

  test("tiene campo de email", async ({ page }) => {
    await expect(page.locator("#email")).toBeVisible();
  });

  test("tiene campo de contraseña", async ({ page }) => {
    await expect(page.locator("#password")).toBeVisible();
  });

  test("tiene campo de PIN", async ({ page }) => {
    await expect(page.locator("#pin")).toBeVisible();
  });

  test("tiene botón de Entrar", async ({ page }) => {
    await expect(page.locator("#btn-login")).toBeVisible();
    await expect(page.locator("#btn-login")).toHaveText("Entrar");
  });

  test("PIN tiene inputmode=numeric", async ({ page }) => {
    const pin = page.locator("#pin");
    await expect(pin).toHaveAttribute("inputmode", "numeric");
  });

  test("PIN tiene maxlength=6", async ({ page }) => {
    await expect(page.locator("#pin")).toHaveAttribute("maxlength", "6");
  });
});

test.describe("Login — validación HTML5", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/index.html");
  });

  test("no envía sin email", async ({ page }) => {
    await page.locator("#password").fill("pass123");
    await page.locator("#pin").fill("1234");
    await page.locator("#btn-login").click();
    // El form no debe navegar — sigue en login
    await expect(page).toHaveURL(/index\.html/);
  });

  test("no envía sin contraseña", async ({ page }) => {
    await page.locator("#email").fill("admin@bananapay.ec");
    await page.locator("#pin").fill("1234");
    await page.locator("#btn-login").click();
    await expect(page).toHaveURL(/index\.html/);
  });
});

test.describe("Login — flujo exitoso", () => {
  test("login correcto redirige al dashboard", async ({ page }) => {
    // Mock del endpoint de login
    await page.route(`${API}/admin/auth/login`, route =>
      route.fulfill({
        json: { token: MOCK_TOKEN, name: "Stanley Admin", role: "admin" },
      })
    );

    await page.goto("/index.html");
    await page.locator("#email").fill("admin@bananapay.ec");
    await page.locator("#password").fill("SuperPass123!");
    await page.locator("#pin").fill("391047");
    await page.locator("#btn-login").click();

    await expect(page).toHaveURL(/dashboard\.html/, { timeout: 5000 });
  });

  test("login guarda el token en localStorage", async ({ page }) => {
    await page.route(`${API}/admin/auth/login`, route =>
      route.fulfill({
        json: { token: MOCK_TOKEN, name: "Stanley Admin", role: "admin" },
      })
    );

    await page.goto("/index.html");
    await page.locator("#email").fill("admin@bananapay.ec");
    await page.locator("#password").fill("SuperPass123!");
    await page.locator("#pin").fill("391047");
    await page.locator("#btn-login").click();

    await page.waitForURL(/dashboard\.html/);
    const token = await page.evaluate(() => localStorage.getItem("bp_token"));
    expect(token).toBe(MOCK_TOKEN);
  });

  test("login guarda el operador en localStorage", async ({ page }) => {
    await page.route(`${API}/admin/auth/login`, route =>
      route.fulfill({
        json: { token: MOCK_TOKEN, name: "Stanley Admin", role: "admin" },
      })
    );

    await page.goto("/index.html");
    await page.locator("#email").fill("admin@bananapay.ec");
    await page.locator("#password").fill("SuperPass123!");
    await page.locator("#pin").fill("391047");
    await page.locator("#btn-login").click();

    await page.waitForURL(/dashboard\.html/);
    const op = await page.evaluate(() => localStorage.getItem("bp_operator"));
    const parsed = JSON.parse(op!);
    expect(parsed.name).toBe("Stanley Admin");
    expect(parsed.role).toBe("admin");
  });
});

test.describe("Login — flujo fallido", () => {
  test.beforeEach(async ({ page }) => {
    await page.route(`${API}/admin/auth/login`, route =>
      route.fulfill({ status: 401, json: { detail: "Credenciales incorrectas" } })
    );
    await page.goto("/index.html");
  });

  test("credenciales incorrectas NO redirigen al dashboard", async ({ page }) => {
    // El 401 en el login endpoint hace que apiFetch redirija a index.html (sí mismo).
    // Lo importante es que el usuario NO llega al dashboard.
    await page.locator("#email").fill("admin@bananapay.ec");
    await page.locator("#password").fill("wrongpassword");
    await page.locator("#pin").fill("000000");
    await page.locator("#btn-login").click();

    await page.waitForTimeout(800);
    await expect(page).not.toHaveURL(/dashboard\.html/);
  });

  test("credenciales incorrectas no guardan token", async ({ page }) => {
    await page.locator("#email").fill("admin@bananapay.ec");
    await page.locator("#password").fill("wrongpassword");
    await page.locator("#pin").fill("000000");
    await page.locator("#btn-login").click();

    await page.waitForTimeout(800);
    const token = await page.evaluate(() => localStorage.getItem("bp_token"));
    expect(token).toBeNull();
  });
});

test.describe("Login — usuario ya autenticado", () => {
  test("si ya hay token redirige al dashboard automáticamente", async ({ page }) => {
    // Inyectar token ANTES de cargar la página
    await page.addInitScript((token) => {
      localStorage.setItem("bp_token", token);
    }, MOCK_TOKEN);

    await page.goto("/index.html");
    await expect(page).toHaveURL(/dashboard\.html/, { timeout: 5000 });
  });
});
