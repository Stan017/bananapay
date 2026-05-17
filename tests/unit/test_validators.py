"""
Tests de validadores de registro KYC.
Cubre: nombre, fecha de nacimiento, dactilar, PIN, cédula, email.
"""

import pytest
from app.utils.validators import (
    validate_full_name,
    validate_birth_date,
    validate_dactilar,
    validate_pin_strength,
    validate_email,
)


class TestValidateFullName:
    def test_nombre_valido_4_palabras(self):
        ok, _ = validate_full_name("Stanley Bolivar Llaguno Caicedo")
        assert ok is True

    def test_nombre_valido_con_tildes(self):
        ok, _ = validate_full_name("María José Pérez López")
        assert ok is True

    def test_solo_2_palabras_es_invalido(self):
        ok, msg = validate_full_name("Juan Pérez")
        assert ok is False
        assert "2" in msg  # mensaje menciona las palabras faltantes

    def test_solo_3_palabras_es_invalido(self):
        ok, _ = validate_full_name("Juan Carlos Pérez")
        assert ok is False

    def test_numeros_en_nombre_es_invalido(self):
        ok, _ = validate_full_name("Juan Carlos Pérez 1ro")
        assert ok is False

    def test_nombre_vacio_es_invalido(self):
        ok, _ = validate_full_name("   ")
        assert ok is False

    def test_guion_en_nombre_es_invalido(self):
        ok, _ = validate_full_name("María-José Pérez López")
        assert ok is False


class TestValidateBirthDate:
    def test_fecha_valida(self):
        ok, _, birth = validate_birth_date("15/03/1990")
        assert ok is True
        assert birth.year  == 1990
        assert birth.month == 3
        assert birth.day   == 15

    def test_acepta_guiones_como_separador(self):
        ok, _, _ = validate_birth_date("15-03-1990")
        assert ok is True

    def test_acepta_puntos_como_separador(self):
        ok, _, _ = validate_birth_date("15.03.1990")
        assert ok is True

    def test_menor_de_18_es_invalido(self):
        ok, msg, _ = validate_birth_date("01/01/2015")
        assert ok is False
        assert "18" in msg

    def test_mayor_de_100_es_invalido(self):
        ok, _, _ = validate_birth_date("01/01/1900")
        assert ok is False

    def test_formato_incorrecto_es_invalido(self):
        ok, _, _ = validate_birth_date("1990-03-15")  # ISO format
        assert ok is False

    def test_fecha_inexistente_es_invalida(self):
        ok, _, _ = validate_birth_date("31/02/1990")  # febrero no tiene 31
        assert ok is False


class TestValidateDactilar:
    def test_dactilar_valido(self):
        ok, _ = validate_dactilar("E4443V2442")
        assert ok is True

    def test_dactilar_minusculas_es_valido(self):
        """Debe convertirse a mayúsculas internamente."""
        ok, _ = validate_dactilar("e4443v2442")
        assert ok is True

    def test_menos_de_10_caracteres_invalido(self):
        ok, _ = validate_dactilar("E4443V244")
        assert ok is False

    def test_mas_de_10_caracteres_invalido(self):
        ok, _ = validate_dactilar("E4443V24420")
        assert ok is False

    def test_solo_numeros_invalido(self):
        """Necesita exactamente 2 letras."""
        ok, _ = validate_dactilar("1234567890")
        assert ok is False

    def test_solo_letras_invalido(self):
        ok, _ = validate_dactilar("ABCDEFGHIJ")
        assert ok is False

    def test_3_letras_invalido(self):
        """Solo se permiten exactamente 2 letras."""
        ok, _ = validate_dactilar("E4A43V2442")
        assert ok is False


class TestValidatePinStrength:
    def test_pin_fuerte_es_valido(self):
        ok, _ = validate_pin_strength("391047")
        assert ok is True

    def test_pin_con_ceros_al_inicio_valido(self):
        ok, _ = validate_pin_strength("001704")
        assert ok is True

    def test_todos_iguales_invalido(self):
        for pin in ["000000", "111111", "999999"]:
            ok, _ = validate_pin_strength(pin)
            assert ok is False, f"{pin} debería ser inválido"

    def test_secuencia_ascendente_invalida(self):
        ok, _ = validate_pin_strength("123456")
        assert ok is False

    def test_secuencia_descendente_invalida(self):
        ok, _ = validate_pin_strength("654321")
        assert ok is False

    def test_pines_comunes_invalidos(self):
        comunes = ["101010", "121212", "112233", "123123"]
        for pin in comunes:
            ok, _ = validate_pin_strength(pin)
            assert ok is False, f"{pin} debería ser inválido"


class TestValidateEmail:
    def test_email_valido(self):
        ok, _ = validate_email("stanley@gmail.com")
        assert ok is True

    def test_email_con_subdomain(self):
        ok, _ = validate_email("user@mail.bananapay.ec")
        assert ok is True

    def test_sin_arroba_invalido(self):
        ok, _ = validate_email("stanleygmail.com")
        assert ok is False

    def test_sin_dominio_invalido(self):
        ok, _ = validate_email("stanley@")
        assert ok is False

    def test_sin_tld_invalido(self):
        ok, _ = validate_email("stanley@gmail")
        assert ok is False

    def test_espacios_invalido(self):
        ok, _ = validate_email("stan ley@gmail.com")
        assert ok is False

    def test_vacio_invalido(self):
        ok, _ = validate_email("")
        assert ok is False
