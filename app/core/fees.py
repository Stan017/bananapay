"""
Lógica de cobro de fees para retiros BananaPay.

TIPO A — Normal  (24h): gratis, mínimo $10
TIPO B — Instant (<1h): fee por tramo, mínimo $10
TIPO C — Express (inmediato desde $1): fee fijo $0.50
"""

from decimal import Decimal
from enum import Enum


class WithdrawalType(str, Enum):
    NORMAL  = "normal"    # gratis, 24h
    INSTANT = "instant"   # fee por tramo, <1h
    EXPRESS = "express"   # fee fijo $0.50, desde $1


# Tramos de retiro instantáneo: (min, max, fee)
INSTANT_TIERS = [
    (Decimal("10.00"),  Decimal("50.00"),  Decimal("0.50")),
    (Decimal("50.01"),  Decimal("100.00"), Decimal("0.75")),
    (Decimal("100.01"), Decimal("999999"), Decimal("1.00")),
]

NORMAL_MINIMUM  = Decimal("10.00")
INSTANT_MINIMUM = Decimal("10.00")
EXPRESS_FEE     = Decimal("0.50")
EXPRESS_MINIMUM = Decimal("1.00")


def calculate_fee(amount: Decimal, withdrawal_type: WithdrawalType) -> Decimal:
    if withdrawal_type == WithdrawalType.NORMAL:
        if amount < NORMAL_MINIMUM:
            raise ValueError(f"Mínimo para retiro normal: ${NORMAL_MINIMUM}")
        return Decimal("0.00")

    if withdrawal_type == WithdrawalType.EXPRESS:
        if amount < EXPRESS_MINIMUM:
            raise ValueError("Monto inválido para retiro express")
        return EXPRESS_FEE

    if withdrawal_type == WithdrawalType.INSTANT:
        if amount < INSTANT_MINIMUM:
            raise ValueError(f"Mínimo para retiro instantáneo: ${INSTANT_MINIMUM}")
        for min_amt, max_amt, fee in INSTANT_TIERS:
            if min_amt <= amount <= max_amt:
                return fee
        return Decimal("1.00")

    raise ValueError("Tipo de retiro inválido")


def get_withdrawal_summary(amount: Decimal, withdrawal_type: WithdrawalType) -> dict:
    """Retorna resumen con monto, fee y monto que recibe el usuario."""
    fee = calculate_fee(amount, withdrawal_type)
    return {
        "amount":          amount,
        "fee":             fee,
        "amount_received": amount - fee,
        "type":            withdrawal_type,
    }


def fee_options_text(amount: Decimal) -> str:
    """Genera el texto con las opciones de fee para mostrar al usuario."""
    if amount < INSTANT_MINIMUM:
        # Solo express disponible
        fee = EXPRESS_FEE
        receives = amount - fee
        return (
            f"💸 Retiro de *${amount:.2f}*\n\n"
            f"⚡ *Express* (única opción para montos menores a $10)\n"
            f"   Fee: *${fee:.2f}* — Recibes: *${receives:.2f}*\n\n"
            "¿Confirmas? Responde *sí* o *no*"
        )

    fee_instant = calculate_fee(amount, WithdrawalType.INSTANT)
    receives_instant = amount - fee_instant
    receives_normal  = amount  # normal es gratis

    return (
        f"💸 Retiro de *${amount:.2f}* — elige cómo:\n\n"
        f"1️⃣ *Normal* (24h)       → *GRATIS*  — recibes *${receives_normal:.2f}*\n"
        f"2️⃣ *Instantáneo* (<1h)  → *${fee_instant:.2f}*    — recibes *${receives_instant:.2f}*\n\n"
        "Responde *1* o *2*:"
    )
