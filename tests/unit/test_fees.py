"""
Tests de cálculo de fees para retiros.
CRÍTICO — un bug aquí cobra de más o de menos a los usuarios.
"""

import pytest
from decimal import Decimal
from app.core.fees import calculate_fee, get_withdrawal_summary, WithdrawalType


class TestRetiroNormal:
    def test_fee_es_cero(self):
        fee = calculate_fee(Decimal("50.00"), WithdrawalType.NORMAL)
        assert fee == Decimal("0.00")

    def test_fee_cero_para_monto_grande(self):
        fee = calculate_fee(Decimal("999.99"), WithdrawalType.NORMAL)
        assert fee == Decimal("0.00")

    def test_monto_minimo_exacto(self):
        """$10.00 exacto debe pasar."""
        fee = calculate_fee(Decimal("10.00"), WithdrawalType.NORMAL)
        assert fee == Decimal("0.00")

    def test_por_debajo_del_minimo_lanza_error(self):
        with pytest.raises(ValueError, match="Mínimo"):
            calculate_fee(Decimal("9.99"), WithdrawalType.NORMAL)

    def test_cero_lanza_error(self):
        with pytest.raises(ValueError):
            calculate_fee(Decimal("0.00"), WithdrawalType.NORMAL)


class TestRetiroExpress:
    def test_fee_fijo_050(self):
        fee = calculate_fee(Decimal("5.00"), WithdrawalType.EXPRESS)
        assert fee == Decimal("0.50")

    def test_fee_fijo_para_cualquier_monto(self):
        """Express siempre cobra $0.50 sin importar el monto."""
        for monto in ["1.00", "5.00", "50.00", "500.00"]:
            fee = calculate_fee(Decimal(monto), WithdrawalType.EXPRESS)
            assert fee == Decimal("0.50"), f"Falló para monto={monto}"

    def test_monto_minimo_exacto(self):
        """$1.00 exacto debe pasar."""
        fee = calculate_fee(Decimal("1.00"), WithdrawalType.EXPRESS)
        assert fee == Decimal("0.50")

    def test_por_debajo_del_minimo_lanza_error(self):
        with pytest.raises(ValueError):
            calculate_fee(Decimal("0.99"), WithdrawalType.EXPRESS)


class TestRetiroInstant:
    def test_tramo_bajo_10_a_50(self):
        fee = calculate_fee(Decimal("10.00"), WithdrawalType.INSTANT)
        assert fee == Decimal("0.50")

    def test_tramo_bajo_limite_superior(self):
        fee = calculate_fee(Decimal("50.00"), WithdrawalType.INSTANT)
        assert fee == Decimal("0.50")

    def test_tramo_medio_5001_a_100(self):
        fee = calculate_fee(Decimal("50.01"), WithdrawalType.INSTANT)
        assert fee == Decimal("0.75")

    def test_tramo_medio_exacto_100(self):
        fee = calculate_fee(Decimal("100.00"), WithdrawalType.INSTANT)
        assert fee == Decimal("0.75")

    def test_tramo_alto_mas_de_100(self):
        fee = calculate_fee(Decimal("100.01"), WithdrawalType.INSTANT)
        assert fee == Decimal("1.00")

    def test_tramo_alto_monto_grande(self):
        fee = calculate_fee(Decimal("5000.00"), WithdrawalType.INSTANT)
        assert fee == Decimal("1.00")

    def test_por_debajo_del_minimo_lanza_error(self):
        with pytest.raises(ValueError, match="Mínimo"):
            calculate_fee(Decimal("9.99"), WithdrawalType.INSTANT)


class TestWithdrawalSummary:
    def test_usuario_recibe_monto_menos_fee(self):
        summary = get_withdrawal_summary(Decimal("50.00"), WithdrawalType.EXPRESS)
        assert summary["amount"]          == Decimal("50.00")
        assert summary["fee"]             == Decimal("0.50")
        assert summary["amount_received"] == Decimal("49.50")

    def test_normal_usuario_recibe_todo(self):
        summary = get_withdrawal_summary(Decimal("100.00"), WithdrawalType.NORMAL)
        assert summary["fee"]             == Decimal("0.00")
        assert summary["amount_received"] == Decimal("100.00")

    def test_instant_50_usuario_recibe_4950(self):
        summary = get_withdrawal_summary(Decimal("50.00"), WithdrawalType.INSTANT)
        assert summary["amount_received"] == Decimal("49.50")

    def test_instant_100_usuario_recibe_9925(self):
        summary = get_withdrawal_summary(Decimal("100.00"), WithdrawalType.INSTANT)
        assert summary["amount_received"] == Decimal("99.25")

    def test_resumen_tiene_todas_las_claves(self):
        summary = get_withdrawal_summary(Decimal("20.00"), WithdrawalType.NORMAL)
        assert "amount"          in summary
        assert "fee"             in summary
        assert "amount_received" in summary
        assert "type"            in summary
