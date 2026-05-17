"""Validadores para campos del registro KYC."""

import re
from datetime import date, datetime


def validate_full_name(name: str) -> tuple[bool, str]:
    """Valida que sean dos nombres y dos apellidos (mínimo 4 palabras)."""
    parts = name.strip().split()
    if len(parts) < 4:
        faltantes = 4 - len(parts)
        return False, (
            f"❌ Necesito *{faltantes} {'palabra más' if faltantes == 1 else 'palabras más'}*.\n\n"
            "Escribe tus *dos nombres y dos apellidos* completos, "
            "tal como aparecen en tu cédula.\n\n"
            "Ejemplo: _María Elena Rodríguez Vega_\n"
            "  • María → primer nombre\n"
            "  • Elena → segundo nombre\n"
            "  • Rodríguez → primer apellido\n"
            "  • Vega → segundo apellido\n\n"
            "Escríbelos de nuevo:"
        )
    if not all(re.match(r"^[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]+$", p) for p in parts):
        return False, "El nombre solo puede tener letras, sin números ni símbolos."
    return True, ""


def validate_birth_date(raw: str) -> tuple[bool, str, date | None]:
    """
    Valida fecha de nacimiento en formato DD/MM/AAAA.
    Edad mínima 18, máxima 100 años.
    """
    raw = raw.strip().replace("-", "/").replace(".", "/")
    try:
        birth = datetime.strptime(raw, "%d/%m/%Y").date()
    except ValueError:
        return False, "Formato incorrecto. Escríbela así: *DD/MM/AAAA* (ej: 15/03/1990)", None

    today = date.today()
    age = (today - birth).days // 365

    if age < 18:
        return False, "Debes tener al menos *18 años* para usar BananaPay.", None
    if age > 100:
        return False, "Fecha de nacimiento no válida.", None

    return True, "", birth


def validate_dactilar(code: str) -> tuple[bool, str]:
    """
    Valida el código dactilar de la cédula ecuatoriana.
    Formato exacto: 10 caracteres, exactamente 2 letras y 8 dígitos intercalados.
    Ejemplo: E4443V2442
    """
    code = code.strip().upper().replace("-", "").replace(" ", "")

    if len(code) != 10:
        return False, (
            "El código dactilar debe tener exactamente *10 caracteres*.\n"
            "Ejemplo: *E4443V2442*\n\n"
            "Lo encuentras en el *reverso* de tu cédula, esquina superior derecha. Intenta de nuevo:"
        )

    letters = sum(1 for c in code if c.isalpha())
    digits = sum(1 for c in code if c.isdigit())

    if letters != 2 or digits != 8:
        return False, (
            "El código dactilar debe tener *2 letras y 8 números*.\n"
            "Ejemplo: *E4443V2442*\n\n"
            "Revisa el reverso de tu cédula e intenta de nuevo:"
        )

    return True, ""


_WEAK_PINS = {
    # Todos iguales
    "000000","111111","222222","333333","444444",
    "555555","666666","777777","888888","999999",
    # Secuencias ascendentes
    "012345","123456","234567","345678","456789","567890",
    # Secuencias descendentes
    "987654","876543","765432","654321","543210","098765",
    # Comunes
    "101010","121212","010101","135790","246810",
    "112233","123123","321321","111222","222333",
}

def validate_pin_strength(pin: str) -> tuple[bool, str]:
    """
    Rechaza PINs débiles: todos iguales, secuencias obvias, PINs conocidos.
    """
    if pin in _WEAK_PINS:
        return False, (
            "❌ Ese PIN es muy fácil de adivinar.\n\n"
            "Evita secuencias como *123456*, números repetidos como *111111* "
            "o tu fecha de nacimiento.\n\n"
            "Crea un PIN de *6 dígitos* que solo tú conozcas:"
        )
    # Todos el mismo dígito (por si no está en la lista)
    if len(set(pin)) == 1:
        return False, (
            "❌ Un PIN con todos los dígitos iguales no es seguro.\n"
            "Elige uno diferente:"
        )
    # Secuencia perfecta (+1 o -1 en cada posición)
    digits = [int(d) for d in pin]
    diffs = [digits[i + 1] - digits[i] for i in range(len(digits) - 1)]
    if len(set(diffs)) == 1 and diffs[0] in (1, -1):
        return False, (
            "❌ Ese PIN es una secuencia obvia (ej: 123456 o 654321).\n"
            "Elige uno más seguro:"
        )
    return True, ""


def validate_email(email: str) -> tuple[bool, str]:
    """Valida formato de email."""
    email = email.strip().lower()
    if not re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", email):
        return False, "El correo no parece válido. Escríbelo de nuevo (ej: tucorreo@gmail.com)"
    return True, ""


def validate_cedula(cedula: str) -> bool:
    """Valida cédula ecuatoriana con algoritmo del Registro Civil."""
    if not cedula.isdigit() or len(cedula) != 10:
        return False
    province = int(cedula[:2])
    if province < 1 or province > 24:
        return False
    if int(cedula[2]) >= 6:
        return False
    coef = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    total = 0
    for i, c in enumerate(coef):
        val = int(cedula[i]) * c
        if val >= 10:
            val -= 9
        total += val
    verifier = 0 if total % 10 == 0 else 10 - (total % 10)
    return verifier == int(cedula[9])
