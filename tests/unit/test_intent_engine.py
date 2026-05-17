"""Tests del motor de intenciones."""

from decimal import Decimal

import pytest

from app.core.intent_engine import Intent, parse_intent


@pytest.mark.parametrize("text,expected_intent", [
    ("hola", Intent.GREETING),
    ("buenas tardes", Intent.GREETING),
    ("ayuda", Intent.HELP),
    ("menú", Intent.HELP),
    ("saldo", Intent.BALANCE),
    ("cuánto tengo", Intent.BALANCE),
    ("mi plata", Intent.BALANCE),
    ("historial", Intent.HISTORY),
    ("mis movimientos", Intent.HISTORY),
    ("depositar", Intent.DEPOSIT),
    ("cargar saldo", Intent.DEPOSIT),
    ("precio BTC", Intent.CRYPTO_PRICE),
    ("precio bitcoin", Intent.CRYPTO_PRICE),
    ("cambiar PIN", Intent.PIN_SETUP),
    ("configurar pin", Intent.PIN_SETUP),
])
def test_basic_intents(text: str, expected_intent: Intent) -> None:
    result = parse_intent(text)
    assert result.intent == expected_intent


def test_transfer_usd() -> None:
    result = parse_intent("enviar 10 a María")
    assert result.intent == Intent.TRANSFER
    assert result.amount == Decimal("10")
    assert result.currency == "USD"
    assert result.raw_recipient == "maría"  # el engine normaliza a minúsculas


def test_transfer_usdt() -> None:
    result = parse_intent("enviar 15 USDT a Juan")
    assert result.intent == Intent.TRANSFER
    assert result.amount == Decimal("15")
    assert result.currency == "USDT"


def test_transfer_phone_number() -> None:
    result = parse_intent("mandar 5 al 0987654321")
    assert result.intent == Intent.TRANSFER
    assert result.amount == Decimal("5")
    assert result.recipient == "+593987654321"


def test_crypto_price() -> None:
    result = parse_intent("precio ETH")
    assert result.intent == Intent.CRYPTO_PRICE
    assert result.currency == "ETH"


def test_buy_crypto() -> None:
    result = parse_intent("comprar 20 de ETH")
    assert result.intent == Intent.CRYPTO_BUY
    assert result.amount == Decimal("20")
    assert result.currency == "ETH"


def test_withdraw_with_amount() -> None:
    result = parse_intent("retirar 50 a mi cuenta")
    assert result.intent == Intent.WITHDRAW
    assert result.amount == Decimal("50")


def test_unknown() -> None:
    result = parse_intent("esto no tiene sentido xyz123")
    assert result.intent == Intent.UNKNOWN
