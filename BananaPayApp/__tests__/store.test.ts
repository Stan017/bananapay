/**
 * Tests del store global Zustand.
 * Verifica las mutaciones de estado: setAuth, setBalances, logout, etc.
 */

import { useStore } from "../src/store/useStore";

// Resetea el store entre tests para evitar contaminación
beforeEach(() => {
  useStore.getState().logout();
});

const TEST_USER = {
  id:     "550e8400-e29b-41d4-a716-446655440000",
  name:   "Stanley Bolivar Llaguno Caicedo",
  phone:  "+593997097262",
  cedula: "0928732494",
};

const TEST_BALANCES = {
  fiat:  100.00,
  usdt:  50.00,
  usdc:  25.00,
  total: 175.00,
};

// ─── Estado inicial ───────────────────────────────────────────────────────────

describe("Estado inicial del store", () => {
  it("token empieza en null", () => {
    expect(useStore.getState().token).toBeNull();
  });

  it("user empieza en null", () => {
    expect(useStore.getState().user).toBeNull();
  });

  it("balances empieza en null", () => {
    expect(useStore.getState().balances).toBeNull();
  });

  it("biometricPending empieza en false", () => {
    expect(useStore.getState().biometricPending).toBe(false);
  });
});

// ─── setAuth ─────────────────────────────────────────────────────────────────

describe("setAuth", () => {
  it("guarda el token", () => {
    useStore.getState().setAuth("mi-token-jwt", TEST_USER);
    expect(useStore.getState().token).toBe("mi-token-jwt");
  });

  it("guarda el usuario", () => {
    useStore.getState().setAuth("mi-token-jwt", TEST_USER);
    expect(useStore.getState().user).toEqual(TEST_USER);
  });

  it("limpia biometricPending al autenticar", () => {
    useStore.setState({ biometricPending: true });
    useStore.getState().setAuth("mi-token-jwt", TEST_USER);
    expect(useStore.getState().biometricPending).toBe(false);
  });

  it("guarda el nombre del usuario correctamente", () => {
    useStore.getState().setAuth("token", TEST_USER);
    expect(useStore.getState().user?.name).toBe("Stanley Bolivar Llaguno Caicedo");
  });

  it("guarda la cédula del usuario correctamente", () => {
    useStore.getState().setAuth("token", TEST_USER);
    expect(useStore.getState().user?.cedula).toBe("0928732494");
  });
});

// ─── setBalances ──────────────────────────────────────────────────────────────

describe("setBalances", () => {
  it("guarda los balances correctamente", () => {
    useStore.getState().setBalances(TEST_BALANCES);
    expect(useStore.getState().balances).toEqual(TEST_BALANCES);
  });

  it("balance fiat es correcto", () => {
    useStore.getState().setBalances(TEST_BALANCES);
    expect(useStore.getState().balances?.fiat).toBe(100.00);
  });

  it("balance total es correcto", () => {
    useStore.getState().setBalances(TEST_BALANCES);
    expect(useStore.getState().balances?.total).toBe(175.00);
  });

  it("puede actualizar balances múltiples veces", () => {
    useStore.getState().setBalances({ fiat: 10, usdt: 0, usdc: 0, total: 10 });
    useStore.getState().setBalances({ fiat: 999, usdt: 0, usdc: 0, total: 999 });
    expect(useStore.getState().balances?.fiat).toBe(999);
  });
});

// ─── setBiometricPending ──────────────────────────────────────────────────────

describe("setBiometricPending", () => {
  it("puede poner biometricPending en true", () => {
    useStore.getState().setBiometricPending(true);
    expect(useStore.getState().biometricPending).toBe(true);
  });

  it("puede poner biometricPending en false", () => {
    useStore.setState({ biometricPending: true });
    useStore.getState().setBiometricPending(false);
    expect(useStore.getState().biometricPending).toBe(false);
  });
});

// ─── logout ───────────────────────────────────────────────────────────────────

describe("logout", () => {
  it("limpia el token", () => {
    useStore.getState().setAuth("mi-token", TEST_USER);
    useStore.getState().logout();
    expect(useStore.getState().token).toBeNull();
  });

  it("limpia el user", () => {
    useStore.getState().setAuth("mi-token", TEST_USER);
    useStore.getState().logout();
    expect(useStore.getState().user).toBeNull();
  });

  it("limpia los balances", () => {
    useStore.getState().setBalances(TEST_BALANCES);
    useStore.getState().logout();
    expect(useStore.getState().balances).toBeNull();
  });

  it("limpia biometricPending", () => {
    useStore.setState({ biometricPending: true });
    useStore.getState().logout();
    expect(useStore.getState().biometricPending).toBe(false);
  });

  it("después de logout el estado es idéntico al inicial", () => {
    useStore.getState().setAuth("token", TEST_USER);
    useStore.getState().setBalances(TEST_BALANCES);
    useStore.getState().setBiometricPending(true);
    useStore.getState().logout();

    const state = useStore.getState();
    expect(state.token).toBeNull();
    expect(state.user).toBeNull();
    expect(state.balances).toBeNull();
    expect(state.biometricPending).toBe(false);
  });
});
