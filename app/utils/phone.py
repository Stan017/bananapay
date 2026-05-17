"""Normalización de números telefónicos ecuatorianos."""

import re

# Acepta: +593XXXXXXXXX, 0593XXXXXXXXX, 593XXXXXXXXX, 0XXXXXXXXX
EC_PHONE_RE = re.compile(r"^(?:\+593|0593|593|0)(\d{9})$")


def normalize_phone(raw: str) -> str | None:
    """Normaliza cualquier formato ecuatoriano a E.164 (+593XXXXXXXXX)."""
    cleaned = re.sub(r"[\s\-().]+", "", raw)
    match = EC_PHONE_RE.match(cleaned)
    if match:
        return f"+593{match.group(1)}"
    return None


def is_valid_cedula(cedula: str) -> bool:
    """Valida cédula ecuatoriana mediante el algoritmo del dígito verificador."""
    if not re.fullmatch(r"\d{10}", cedula):
        return False

    province = int(cedula[:2])
    if not (1 <= province <= 24):
        return False

    digits = [int(d) for d in cedula]
    total = 0
    for i, d in enumerate(digits[:9]):
        val = d * 2 if i % 2 == 0 else d
        if val >= 10:
            val -= 9
        total += val

    verifier = (10 - (total % 10)) % 10
    return verifier == digits[9]
