"""Formateo y parseo de montos USD y crypto."""

from decimal import Decimal, InvalidOperation


def parse_amount(raw: str) -> Decimal | None:
    """Parsea un string de monto. Acepta $, coma o punto como separador decimal."""
    cleaned = raw.strip().lstrip("$").strip().replace(",", ".")
    try:
        amount = Decimal(cleaned)
        return amount if amount > 0 else None
    except InvalidOperation:
        return None


def format_usd(amount: Decimal) -> str:
    return f"${amount:,.2f} USD"


def format_crypto(amount: Decimal, symbol: str) -> str:
    """Formatea un monto crypto sin ceros finales innecesarios."""
    formatted = f"{amount:.8f}".rstrip("0").rstrip(".")
    return f"{formatted} {symbol}"
