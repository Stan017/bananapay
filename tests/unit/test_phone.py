"""Tests de normalización de teléfono y validación de cédula."""

import pytest

from app.utils.phone import is_valid_cedula, normalize_phone


@pytest.mark.parametrize("raw,expected", [
    ("0987654321", "+593987654321"),
    ("+593987654321", "+593987654321"),
    ("593987654321", "+593987654321"),
    ("0593987654321", "+593987654321"),
    ("098 765 4321", "+593987654321"),
    ("123", None),
    ("not-a-phone", None),
])
def test_normalize_phone(raw: str, expected: str | None) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("cedula,valid", [
    ("1713175071", True),   # cédula válida de ejemplo
    ("0000000000", False),  # provincia inválida
    ("123456789", False),   # longitud incorrecta
    ("17131750711", False), # demasiado larga
    ("abcdefghij", False),  # no numérica
])
def test_is_valid_cedula(cedula: str, valid: bool) -> None:
    assert is_valid_cedula(cedula) == valid
