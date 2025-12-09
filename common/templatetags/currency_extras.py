# common/templatetags/currency_extras.py
from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()

@register.filter
def money_mx(value):
    """
    Formatea un número como moneda MX:
    230      -> '230.00'
    2300     -> '2,300.00'
    2300.5   -> '2,300.50'
    """
    if value in (None, ""):
        return ""

    try:
        value = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return ""

    # Usa formato "en-US": coma miles, punto decimales
    return f"{value:,.2f}"
