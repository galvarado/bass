from django import template

register = template.Library()

_UNITS = {
    0: "cero", 1: "uno", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco",
    6: "seis", 7: "siete", 8: "ocho", 9: "nueve", 10: "diez",
    11: "once", 12: "doce", 13: "trece", 14: "catorce", 15: "quince",
    16: "dieciséis", 17: "diecisiete", 18: "dieciocho", 19: "diecinueve",
    20: "veinte", 21: "veintiuno", 22: "veintidós", 23: "veintitrés",
    24: "veinticuatro", 25: "veinticinco", 26: "veintiséis",
    27: "veintisiete", 28: "veintiocho", 29: "veintinueve",
}

_TENS = {
    30: "treinta", 40: "cuarenta", 50: "cincuenta",
    60: "sesenta", 70: "setenta", 80: "ochenta", 90: "noventa",
}

_HUNDREDS = {
    100: "cien", 200: "doscientos", 300: "trescientos", 400: "cuatrocientos",
    500: "quinientos", 600: "seiscientos", 700: "setecientos",
    800: "ochocientos", 900: "novecientos",
}

def _to_words_es(n: int) -> str:
    if n in _UNITS:
        return _UNITS[n]
    if n < 100:
        ten = (n // 10) * 10
        unit = n % 10
        if unit == 0:
            return _TENS[ten]
        return f"{_TENS[ten]} y {_UNITS[unit]}"
    if n < 1000:
        hundred = (n // 100) * 100
        rest = n % 100
        if n == 100:
            return "cien"
        prefix = "ciento" if hundred == 100 else _HUNDREDS.get(hundred, "")
        return prefix if rest == 0 else f"{prefix} {_to_words_es(rest)}"
    if n < 1000000:
        thousands = n // 1000
        rest = n % 1000
        if thousands == 1:
            head = "mil"
        else:
            head = f"{_to_words_es(thousands)} mil"
        return head if rest == 0 else f"{head} {_to_words_es(rest)}"

    # Si algún día te llega más grande, lo puedes extender aquí.
    return str(n)

@register.filter
def number_to_words_es(value):
    """
    Convierte enteros a letras (ES) para PDF.
    Ej: 2 -> "dos"
    """
    try:
        n = int(value)
    except (TypeError, ValueError):
        return ""
    return _to_words_es(n)
