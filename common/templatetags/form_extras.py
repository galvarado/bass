from django import template
register = template.Library()

@register.filter(name="add_class")
def add_class(field, css):
    """
    Agrega clases CSS al campo y aplica 'is-invalid' automáticamente si hay errores.
    Ej: {{ form.nombre|add_class:"form-control" }}
    """
    attrs = field.field.widget.attrs.copy()
    existing = attrs.get("class", "")
    classes = (existing + " " + css).strip()

    # Agrega 'is-invalid' si el campo tiene errores
    if field.errors:
        classes += " is-invalid"

    attrs["class"] = classes
    return field.as_widget(attrs=attrs)
