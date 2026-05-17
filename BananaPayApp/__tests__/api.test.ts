/**
 * Tests del módulo api.ts — mockea axios, verifica que
 * las funciones llamen los endpoints correctos y manejen errores.
 */

// Obtenemos la instancia mock que crea axios.create()
const mockAxios = require("axios").__mockInstance;

import {
  login,
  getBalance,
  getHistory,
  getProfile,
  sendTransfer,
  updatePushToken,
} from "../src/services/api";

beforeEach(() => {
  jest.clearAllMocks();
});

// ─── login ────────────────────────────────────────────────────────────────────

describe("login()", () => {
  it("llama POST /app/auth/login", async () => {
    mockAxios.post.mockResolvedValue({
      data: { token: "jwt-test", user_id: "uuid-1", name: "Stanley", phone: "+593997097262" },
    });

    await login("0928732494", "0997097262", "001704");

    expect(mockAxios.post).toHaveBeenCalledWith(
      "/app/auth/login",
      { cedula: "0928732494", phone: "0997097262", pin: "001704" }
    );
  });

  it("retorna los datos del usuario", async () => {
    const mockData = { token: "jwt-test", user_id: "uuid-1", name: "Stanley", phone: "+593997097262" };
    mockAxios.post.mockResolvedValue({ data: mockData });

    const result = await login("0928732494", "0997097262", "001704");
    expect(result).toEqual(mockData);
  });

  it("propaga el error si el login falla", async () => {
    mockAxios.post.mockRejectedValue({ response: { status: 401 } });
    await expect(login("0928732494", "0997097262", "wrong")).rejects.toBeTruthy();
  });
});

// ─── getBalance ───────────────────────────────────────────────────────────────

describe("getBalance()", () => {
  it("llama GET /app/me/balance", async () => {
    mockAxios.get.mockResolvedValue({
      data: { fiat: 100, usdt: 0, usdc: 0, total: 100 },
    });

    await getBalance();
    expect(mockAxios.get).toHaveBeenCalledWith("/app/me/balance");
  });

  it("retorna los balances correctos", async () => {
    const balances = { fiat: 55.50, usdt: 10, usdc: 0, total: 65.50 };
    mockAxios.get.mockResolvedValue({ data: balances });

    const result = await getBalance();
    expect(result).toEqual(balances);
  });

  it("propaga error 401 si el token expiró", async () => {
    mockAxios.get.mockRejectedValue({ response: { status: 401 } });
    await expect(getBalance()).rejects.toBeTruthy();
  });
});

// ─── getHistory ───────────────────────────────────────────────────────────────

describe("getHistory()", () => {
  it("llama GET /app/me/history con limit por defecto 20", async () => {
    mockAxios.get.mockResolvedValue({ data: [] });
    await getHistory();
    expect(mockAxios.get).toHaveBeenCalledWith("/app/me/history?limit=20");
  });

  it("respeta el limit personalizado", async () => {
    mockAxios.get.mockResolvedValue({ data: [] });
    await getHistory(5);
    expect(mockAxios.get).toHaveBeenCalledWith("/app/me/history?limit=5");
  });

  it("retorna lista de transacciones", async () => {
    const txs = [{ id: "tx-1", amount: 20, direction: "out" }];
    mockAxios.get.mockResolvedValue({ data: txs });

    const result = await getHistory();
    expect(result).toEqual(txs);
  });
});

// ─── getProfile ───────────────────────────────────────────────────────────────

describe("getProfile()", () => {
  it("llama GET /app/me/profile", async () => {
    mockAxios.get.mockResolvedValue({
      data: { id: "uuid", name: "Stanley", phone: "+593997097262", cedula: "0928732494" },
    });

    await getProfile();
    expect(mockAxios.get).toHaveBeenCalledWith("/app/me/profile");
  });

  it("retorna datos del perfil sin pin_hash", async () => {
    const profile = { id: "uuid", name: "Stanley", phone: "+593997097262", cedula: "0928732494" };
    mockAxios.get.mockResolvedValue({ data: profile });

    const result = await getProfile();
    expect(result).not.toHaveProperty("pin_hash");
  });
});

// ─── sendTransfer ─────────────────────────────────────────────────────────────

describe("sendTransfer()", () => {
  const transferPayload = {
    to_cedula: "1234567890",
    to_phone:  "0991234567",
    amount:    50,
    currency:  "USD",
    pin:       "001704",
  };

  it("llama POST /app/transfer/send", async () => {
    mockAxios.post.mockResolvedValue({ data: { ok: true, tx_id: "tx-abc" } });

    await sendTransfer(transferPayload);
    expect(mockAxios.post).toHaveBeenCalledWith("/app/transfer/send", transferPayload);
  });

  it("retorna confirmación de la transferencia", async () => {
    mockAxios.post.mockResolvedValue({ data: { ok: true, tx_id: "tx-abc" } });

    const result = await sendTransfer(transferPayload);
    expect(result.ok).toBe(true);
  });

  it("propaga error si saldo insuficiente", async () => {
    mockAxios.post.mockRejectedValue({ response: { status: 400, data: { detail: "Saldo insuficiente" } } });
    await expect(sendTransfer(transferPayload)).rejects.toBeTruthy();
  });

  it("propaga error si PIN incorrecto", async () => {
    mockAxios.post.mockRejectedValue({ response: { status: 401 } });
    await expect(sendTransfer({ ...transferPayload, pin: "000000" })).rejects.toBeTruthy();
  });
});

// ─── updatePushToken ──────────────────────────────────────────────────────────

describe("updatePushToken()", () => {
  it("llama PATCH /app/me/push-token", async () => {
    mockAxios.patch.mockResolvedValue({ data: { ok: true } });

    await updatePushToken("ExponentPushToken[test-123]");
    expect(mockAxios.patch).toHaveBeenCalledWith(
      "/app/me/push-token",
      { token: "ExponentPushToken[test-123]" }
    );
  });

  it("retorna ok: true en éxito", async () => {
    mockAxios.patch.mockResolvedValue({ data: { ok: true } });

    const result = await updatePushToken("ExponentPushToken[test-123]");
    expect(result.ok).toBe(true);
  });
});
