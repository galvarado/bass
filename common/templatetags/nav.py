from django import template

register = template.Library()

@register.filter
def startswith(value, arg):
    """Uso: {{ request.path|startswith:'/clients/' }} -> True/False"""
    try:
        return str(value).startswith(str(arg))
    except Exception:
        return False

@register.filter
def startswith_any(value, args):
    """
    Uso: {{ request.path|startswith_any:'/a/,/b/,/c/' }} -> True/False
    'args' es una lista separada por comas.
    """
    v = str(value)
    prefixes = [a.strip() for a in str(args).split(',') if a.strip()]
    return any(v.startswith(p) for p in prefixes)
