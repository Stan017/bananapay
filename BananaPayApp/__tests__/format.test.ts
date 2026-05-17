/**
 * Tests de funciones de formato — sin dependencias nativas.
 * fmtUSD · fmtCrypto · fmtDate
 */

import { fmtUSD, fmtCrypto, fmtDate } from "../src/utils/format";

// ─── fmtUSD ──────────────────────────────────────────────────────────────────

describe("fmtUSD", () => {
  it("formatea entero sin decimales extra", () => {
    expect(fmtUSD(100)).toBe("$100.00");
  });

  it("formatea cero correctamente", () => {
    expect(fmtUSD(0)).toBe("$0.00");
  });

  it("formatea centavos", () => {
    expect(fmtUSD(0.5)).toBe("$0.50");
  });

  it("agrega coma de miles a $1000", () => {
    expect(fmtUSD(1000)).toBe("$1,000.00");
  });

  it("agrega coma de miles a $1000000", () => {
    expect(fmtUSD(1_000_000)).toBe("$1,000,000.00");
  });

  it("redondea a 2 decimales", () => {
    expect(fmtUSD(1.999)).toBe("$2.00");
  });

  it("formatea monto típico de transferencia", () => {
    expect(fmtUSD(55.75)).toBe("$55.75");
  });

  it("siempre empieza con $", () => {
    expect(fmtUSD(42)).toMatch(/^\$/);
  });

  it("formatea $9999.99 correctamente", () => {
    expect(fmtUSD(9999.99)).toBe("$9,999.99");
  });
});

// ─── fmtCrypto ───────────────────────────────────────────────────────────────

describe("fmtCrypto", () => {
  it("formatea USDT con símbolo", () => {
    expect(fmtCrypto(10.5, "USDT")).toBe("10.50 USDT");
  });

  it("formatea USDC con símbolo", () => {
    expect(fmtCrypto(25, "USDC")).toBe("25.00 USDC");
  });

  it("formatea cero USDT", () => {
    expect(fmtCrypto(0, "USDT")).toBe("0.00 USDT");
  });

  it("usa la moneda pasada como parámetro", () => {
    expect(fmtCrypto(1, "BTC")).toContain("BTC");
  });

  it("tiene exactamente 2 decimales", () => {
    const result = fmtCrypto(1.1, "USDT");
    expect(result).toBe("1.10 USDT");
  });
});

// ─── fmtDate ─────────────────────────────────────────────────────────────────

describe("fmtDate", () => {
  it("retorna string vacío para input vacío", () => {
    expect(fmtDate("")).toBe("");
  });

  it("retorna string vacío para undefined/null", () => {
    expect(fmtDate(null as any)).toBe("");
  });

  it("parsea ISO date y retorna string localizado", () => {
    const result = fmtDate("2024-05-10T10:00:00");
    expect(result).toBeTruthy();
    expect(typeof result).toBe("string");
  });

  it("incluye el año en el resultado", () => {
    const result = fmtDate("2024-05-10T10:00:00");
    expect(result).toContain("2024");
  });

  it("incluye el día en el resultado", () => {
    const result = fmtDate("2024-05-10T10:00:00");
    expect(result).toContain("10");
  });
});
