from django import template
from django.forms.boundfield import BoundField

register = template.Library()

@register.filter(name="add_class")
def add_class(field, css):
    """
    Agrega clases CSS al campo y aplica 'is-invalid' si hay errores.
    Tolera valores no-BoundField (p.ej. strings) devolviendo el valor tal cual.
    """
    # 1) Si no es un BoundField (p.ej. string ya renderizado), no toques nada
    if not isinstance(field, BoundField):
        return field

    # 2) Mezcla clases existentes del widget con las nuevas
    attrs = (field.field.widget.attrs or {}).copy()
    existing = attrs.get("class", "")
    classes = (existing + " " + (css or "")).strip()

    # 3) Agrega is-invalid si hay errores y evita duplicados
    if getattr(field, "errors", None):
        if "is-invalid" not in classes:
            classes += " is-invalid"

    attrs["class"] = classes

    # 4) Renderiza el widget con los attrs combinados
    return field.as_widget(attrs=attrs)
