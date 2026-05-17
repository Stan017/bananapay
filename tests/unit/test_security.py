"""
Tests de seguridad: hashing y verificación de PIN.
Crítico — un bug aquí bloquea a todos los usuarios o compromete la app.
"""

import pytest
from app.core.security import hash_pin, verify_pin


class TestHashPin:
    def test_produce_un_hash(self):
        """hash_pin debe retornar un string no vacío."""
        result = hash_pin("123456")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_no_es_el_pin_en_plano(self):
        """El hash nunca debe contener el PIN en texto plano."""
        pin = "001704"
        result = hash_pin(pin)
        assert pin not in result

    def test_hashes_distintos_para_el_mismo_pin(self):
        """bcrypt usa salt aleatorio — dos hashes del mismo PIN son distintos."""
        h1 = hash_pin("123456")
        h2 = hash_pin("123456")
        assert h1 != h2

    def test_formato_bcrypt(self):
        """El hash debe empezar con $2b$ (bcrypt)."""
        result = hash_pin("123456")
        assert result.startswith("$2b$")

    def test_pin_con_ceros_al_inicio(self):
        """PINs como '001704' no deben perder los ceros."""
        h = hash_pin("001704")
        assert verify_pin("001704", h)
        assert not verify_pin("1704", h)


class TestVerifyPin:
    def test_pin_correcto_retorna_true(self):
        pin = "654321"
        h   = hash_pin(pin)
        assert verify_pin(pin, h) is True

    def test_pin_incorrecto_retorna_false(self):
        h = hash_pin("654321")
        assert verify_pin("000000", h) is False

    def test_pin_con_espacio_retorna_false(self):
        """Un PIN con espacio accidental no debe coincidir."""
        h = hash_pin("123456")
        assert verify_pin("123456 ", h) is False
        assert verify_pin(" 123456", h) is False

    def test_pin_vacio_retorna_false(self):
        h = hash_pin("123456")
        assert verify_pin("", h) is False

    def test_todos_los_digitos_posibles(self):
        """Verifica que todos los dígitos 0-9 funcionan correctamente."""
        for d in "0123456789":
            pin = d * 6
            h   = hash_pin(pin)
            assert verify_pin(pin, h) is True
            assert verify_pin("999999" if d != "9" else "000000", h) is False
