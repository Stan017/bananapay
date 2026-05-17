"""
trongrid.py — Cliente para TronGrid API
════════════════════════════════════════
Consulta transacciones TRC-20 entrantes a una dirección TRON.
Soporta cualquier token TRC-20: USDT, USDC, etc.

TronGrid docs: https://developers.tron.network/reference/get-trc20-transaction-info-by-account-address

Registro gratuito en: https://www.trongrid.io/
Sin API key: funciona pero con rate limit bajo (1 req/s)
Con API key: 15 req/s en tier gratuito
"""

from __future__ import annotations

import asyncio

import httpx

from app.utils.logger import get_logger

_MAX_ATTEMPTS = 3
_BASE_DELAY   = 1.0

logger = get_logger(__name__)

# ─── Contratos TRC-20 soportados ─────────────────────────────────────────────
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"   # USDT TRC-20 mainnet
USDC_CONTRACT = "TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8"    # USDC TRC-20 mainnet
                                                          # ↑ verificar en tronscan.org antes de producción

TRONGRID_BASE = "https://api.trongrid.io"

# Mapa contrato → nombre de moneda (para logs y acreditación)
CONTRACT_CURRENCY: dict[str, str] = {
    USDT_CONTRACT: "USDT",
    USDC_CONTRACT: "USDC",
}


def _headers() -> dict:
    from app.config import settings
    h = {"Accept": "application/json"}
    if settings.trongrid_api_key:
        h["TRON-PRO-API-KEY"] = settings.trongrid_api_key
    return h


async def get_incoming_trc20(
    address: str,
    contract_address: str,
    min_timestamp_ms: int | None = None,
    limit: int = 20,
) -> list[dict]:
    """
    Retorna las transacciones TRC-20 entrantes a `address` para el contrato dado.

    Args:
        address:           Dirección TRC-20 del usuario (T...)
        contract_address:  Contrato del token (USDT_CONTRACT, USDC_CONTRACT, etc.)
        min_timestamp_ms:  Solo transacciones más nuevas que este timestamp (ms)
        limit:             Máximo de resultados

    Returns:
        Lista de dicts con:
          {
            tx_hash:      str,
            from_address: str,
            to_address:   str,
            amount:       float,   # ya dividido por 10^6
            currency:     str,     # "USDT" | "USDC"
            block_number: int,
            timestamp_ms: int,
          }
    """
    currency = CONTRACT_CURRENCY.get(contract_address, "UNKNOWN")
    url      = f"{TRONGRID_BASE}/v1/accounts/{address}/transactions/trc20"
    params: dict = {
        "contract_address": contract_address,
        "only_to":          "true",
        "limit":            str(limit),
        "order_by":         "block_timestamp,desc",
    }
    if min_timestamp_ms:
        params["min_timestamp"] = str(min_timestamp_ms)

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params, headers=_headers())

            if resp.status_code == 200:
                data   = resp.json()
                result = []
                for tx in data.get("data", []):
                    try:
                        raw_value = int(tx.get("value", "0"))
                        amount    = raw_value / 1_000_000   # 6 decimales para USDT y USDC
                        if amount <= 0:
                            continue
                        result.append({
                            "tx_hash":      tx["transaction_id"],
                            "from_address": tx["from"],
                            "to_address":   tx["to"],
                            "amount":       amount,
                            "currency":     currency,
                            "block_number": tx.get("blockNumber") or tx.get("block_number"),
                            "timestamp_ms": tx.get("block_timestamp", 0),
                        })
                    except (KeyError, ValueError):
                        continue
                return result

            if resp.status_code == 429 or resp.status_code >= 500:
                last_exc = Exception(f"HTTP {resp.status_code}")
                logger.warning("trongrid: HTTP %s intento %d/%d para %s [%s]",
                               resp.status_code, attempt, _MAX_ATTEMPTS, address[:12], currency)
            else:
                logger.warning("trongrid: HTTP %s (no reintentable) para %s [%s] — %s",
                               resp.status_code, address, currency, resp.text[:100])
                return []

        except httpx.TimeoutException as exc:
            last_exc = exc
            logger.warning("trongrid: timeout intento %d/%d para %s [%s]",
                           attempt, _MAX_ATTEMPTS, address[:12], currency)
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            last_exc = exc
            logger.warning("trongrid: red %s intento %d/%d para %s [%s]",
                           type(exc).__name__, attempt, _MAX_ATTEMPTS, address[:12], currency)
        except Exception as exc:
            logger.error("trongrid: error inesperado [%s] — %s", currency, exc)
            return []

        if attempt < _MAX_ATTEMPTS:
            await asyncio.sleep(_BASE_DELAY * (2 ** (attempt - 1)))

    logger.error("trongrid: todos los intentos fallaron para %s [%s]", address[:12], currency)
    return []


async def get_incoming_usdt(
    address: str,
    min_timestamp_ms: int | None = None,
    limit: int = 20,
) -> list[dict]:
    """Alias de compatibilidad — usa get_incoming_trc20 con contrato USDT."""
    return await get_incoming_trc20(address, USDT_CONTRACT, min_timestamp_ms, limit)
