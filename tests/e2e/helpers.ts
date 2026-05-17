/**
 * Helpers compartidos para los tests E2E del panel admin.
 * Mockea el API usando page.route() — no necesita backend real.
 */

import { Page } from "@playwright/test";

export const API = "http://localhost:8000";

export const MOCK_OPERATOR = { name: "Stanley Admin", role: "admin" };
export const MOCK_TOKEN    = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.mock";

export const MOCK_METRICS = {
  float_total:          12345.67,
  float_fiat:           10000.00,
  float_usdt:           1500.00,
  float_usdc:           845.67,
  users_total:          238,
  users_new_today:      5,
  deposits_pending:     3,
  withdrawals_pending:  1,
  fees_today:           45.50,
  fees_month:           1280.00,
  volume_today:         8900.00,
};

export const MOCK_DEPOSIT = {
  id:               "aaaabbbb-1111-2222-3333-ccccddddeeee",
  amount:           150.00,
  bank_name:        "Banco Pichincha",
  reference_number: "REF-2024-001",
  status:           "pending",
  created_at:       "2024-05-10T10:00:00Z",
  user: {
    name:   "Stanley Bolivar Llaguno Caicedo",
    cedula: "0928732494",
    phone:  "+593997097262",
  },
};

export const MOCK_WITHDRAWAL = {
  id:              "bbbbcccc-2222-3333-4444-ddddeeeeffff",
  amount:          200.00,
  amount_received: 197.00,
  fee:             3.00,
  bank_name:       "Banco Guayaquil",
  account_type:    "Corriente",
  account_number:  "1234567890",
  account_holder:  "Stanley Llaguno",
  withdrawal_type: "instant",
  status:          "pending",
  created_at:      "2024-05-10T11:00:00Z",
  user: {
    name:  "Stanley Bolivar Llaguno Caicedo",
    phone: "+593997097262",
  },
};

/**
 * Inyecta token + operador en localStorage para simular sesión activa.
 */
export async function setLoggedIn(page: Page): Promise<void> {
  await page.addInitScript(({ token, operator }) => {
    localStorage.setItem("bp_token", token);
    localStorage.setItem("bp_operator", JSON.stringify(operator));
  }, { token: MOCK_TOKEN, operator: MOCK_OPERATOR });
}

/**
 * Mockea todos los endpoints del API que usan las páginas del panel.
 *
 * IMPORTANTE: en Playwright el último route registrado tiene MAYOR prioridad.
 * Por eso el catch-all va PRIMERO y los específicos van después.
 */
export async function mockAllRoutes(page: Page): Promise<void> {
  // ── Catch-all PRIMERO (menor prioridad — solo aplica si nada más matchea) ──
  await page.route(`${API}/**`, route =>
    route.fulfill({ status: 200, json: {} })
  );

  // ── Rutas específicas (mayor prioridad por estar registradas después) ──────

  // Gastos
  await page.route(`${API}/admin/dashboard/expenses`, route =>
    route.fulfill({ json: [] })
  );

  // Historial
  await page.route(`${API}/admin/history/**`, route =>
    route.fulfill({ json: { data: [] } })
  );

  // Usuarios
  await page.route(`${API}/admin/users/search*`, route =>
    route.fulfill({ json: [] })
  );

  // Soporte y fraude
  await page.route(`${API}/admin/support/pending`, route =>
    route.fulfill({ json: [] })
  );
  await page.route(`${API}/admin/fraud/alerts`, route =>
    route.fulfill({ json: { alerts: [], total: 0 } })
  );
  await page.route(`${API}/admin/fraud/blacklist`, route =>
    route.fulfill({ json: { blacklist: [] } })
  );
  await page.route(`${API}/admin/fraud/config`, route =>
    route.fulfill({ json: { config: [] } })
  );

  // Retiros
  await page.route(`${API}/admin/withdrawals/*/approve`, route =>
    route.fulfill({ json: { ok: true } })
  );
  await page.route(`${API}/admin/withdrawals/*/reject`, route =>
    route.fulfill({ json: { ok: true } })
  );
  await page.route(`${API}/admin/withdrawals/pending`, route =>
    route.fulfill({ json: [MOCK_WITHDRAWAL] })
  );

  // Depósitos
  await page.route(`${API}/admin/deposits/*/approve`, route =>
    route.fulfill({ json: { ok: true } })
  );
  await page.route(`${API}/admin/deposits/*/reject`, route =>
    route.fulfill({ json: { ok: true } })
  );
  await page.route(`${API}/admin/deposits/pending`, route =>
    route.fulfill({ json: [MOCK_DEPOSIT] })
  );

  // Dashboard metrics (más específicos al final = mayor prioridad)
  await page.route(`${API}/admin/dashboard/analytics*`, route =>
    route.fulfill({ json: {
      volume_by_day:    [],
      deposit_rates:    { approved: 40, rejected: 5, pending: 3 },
      deposits_by_bank: [],
      new_users_by_day: [],
      avg_approval_minutes: 12,
    }})
  );
  await page.route(`${API}/admin/dashboard/pnl*`, route =>
    route.fulfill({ json: [] })
  );
  await page.route(`${API}/admin/dashboard/fees`, route =>
    route.fulfill({ json: { fees_today: 45.50, fees_month: 1280.00 } })
  );
  // ÚLTIMO = MAYOR PRIORIDAD
  await page.route(`${API}/admin/dashboard`, route =>
    route.fulfill({ json: MOCK_METRICS })
  );
}
