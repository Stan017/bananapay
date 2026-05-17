"""
Tests de parseo y formateo de montos.
Un bug aquí puede mostrar balances incorrectos o parsear montos mal.
"""

import pytest
from decimal import Decimal
from app.utils.currency import parse_amount, format_usd, format_crypto


class TestParseAmount:
    def test_numero_simple(self):
        assert parse_amount("10") == Decimal("10")

    def test_con_decimales_punto(self):
        assert parse_amount("10.50") == Decimal("10.50")

    def test_con_decimales_coma(self):
        """En Ecuador se usa coma como separador decimal."""
        assert parse_amount("10,50") == Decimal("10.50")

    def test_con_signo_dolar(self):
        assert parse_amount("$25.00") == Decimal("25.00")

    def test_con_espacios(self):
        assert parse_amount("  50.00  ") == Decimal("50.00")

    def test_cero_retorna_none(self):
        assert parse_amount("0") is None

    def test_negativo_retorna_none(self):
        assert parse_amount("-10") is None

    def test_texto_retorna_none(self):
        assert parse_amount("veinte") is None

    def test_vacio_retorna_none(self):
        assert parse_amount("") is None

    def test_solo_signo_dolar_retorna_none(self):
        assert parse_amount("$") is None

    def test_monto_grande(self):
        result = parse_amount("9999.99")
        assert result == Decimal("9999.99")

    def test_un_centavo(self):
        assert parse_amount("0.01") == Decimal("0.01")


class TestFormatUsd:
    def test_formato_basico(self):
        assert format_usd(Decimal("10.50")) == "$10.50 USD"

    def test_cero(self):
        assert format_usd(Decimal("0.00")) == "$0.00 USD"

    def test_miles_con_coma(self):
        assert format_usd(Decimal("1000.00")) == "$1,000.00 USD"

    def test_millones(self):
        assert format_usd(Decimal("1000000.00")) == "$1,000,000.00 USD"

    def test_redondeo_dos_decimales(self):
        result = format_usd(Decimal("10.5"))
        assert result == "$10.50 USD"


class TestFormatCrypto:
    def test_formato_usdt(self):
        result = format_crypto(Decimal("85.50"), "USDT")
        assert "85.5" in result
        assert "USDT" in result

    def test_elimina_ceros_finales(self):
        result = format_crypto(Decimal("100.00000000"), "USDT")
        assert "100" in result
        assert "00000" not in result

    def test_formato_usdc(self):
        result = format_crypto(Decimal("50.00"), "USDC")
        assert "USDC" in result

    def test_cantidad_pequena_con_decimales(self):
        result = format_crypto(Decimal("0.00123456"), "BTC")
        assert "0.00123456" in result
        assert "BTC" in result

    def test_no_incluye_ceros_innecesarios(self):
        result = format_crypto(Decimal("1.50000000"), "USDT")
        assert result == "1.5 USDT"
