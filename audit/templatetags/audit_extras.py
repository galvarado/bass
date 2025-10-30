# audit/templatetags/audit_extras.py
from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe
import json

register = template.Library()


# ===============================
# === TAGS / FILTROS PRINCIPALES ===
# ===============================

@register.filter
def action_badge(action):
    """Devuelve una etiqueta con color según el tipo de acción."""
    colors = {
        "create": "success",
        "update": "warning",
        "delete": "danger",
        "restore": "info",
        "login": "primary",
        "logout": "secondary",
    }
    label = {
        "create": "Creación",
        "update": "Actualización",
        "delete": "Eliminación",
        "restore": "Restauración",
        "login": "Inicio de sesión",
        "logout": "Cierre de sesión",
    }.get(action, action.capitalize())

    color = colors.get(action, "light")
    return format_html('<span class="badge badge-{}">{}</span>', color, label)


@register.filter
def target_label(log):
    """Muestra el objeto o modelo afectado por la acción."""
    if getattr(log, "object_repr", None):
        return log.object_repr
    if getattr(log, "content_type", None):
        return str(log.content_type).capitalize()
    return "—"


@register.filter
def changed_keys(changes):
    """Devuelve las llaves de los campos modificados."""
    if not changes:
        return []
    return list(changes.keys())


@register.filter
def change_summary(changes, limit=3):
    """Muestra los primeros N campos cambiados."""
    if not changes:
        return ""
    keys = list(changes.keys())[:limit]
    html = ", ".join(keys)
    if len(changes) > limit:
        html += "..."
    return html


# =====================================
# === FORMATEO DE DIFERENCIAS (tabla) ===
# =====================================

@register.filter
def diff_table(changes):
    """
    Renderiza una tabla HTML con los cambios detectados.
    Limpia listas como ['valor viejo', 'valor nuevo'] y muestra solo los textos planos.
    """
    if not changes:
        return ""

    html = [
        '<table class="table table-sm mb-0 small">',
        "<thead><tr><th>Campo</th><th>Antes</th><th>Después</th></tr></thead>",
        "<tbody>",
    ]

    for field, pair in changes.items():
        old_val, new_val = None, None

        # Estructuras típicas: [old, new], tuple, o dict
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            old_val, new_val = pair
        elif isinstance(pair, dict) and {"old", "new"} <= pair.keys():
            old_val, new_val = pair["old"], pair["new"]
        else:
            # fallback
            new_val = pair

        # Si alguno de los valores es lista, lo aplanamos
        if isinstance(old_val, (list, tuple)):
            old_val = ", ".join(str(x) for x in old_val)
        if isinstance(new_val, (list, tuple)):
            new_val = ", ".join(str(x) for x in new_val)

        # Limpieza visual
        old_val = "—" if old_val in (None, "", [], {}, "None") else str(old_val)
        new_val = "—" if new_val in (None, "", [], {}, "None") else str(new_val)

        html.append(
            f"<tr>"
            f"<td>{field}</td>"
            f"<td>{old_val}</td>"
            f"<td class='bg-success-light'>{new_val}</td>"
            f"</tr>"
        )

    html.append("</tbody></table>")
    return mark_safe("".join(html))


# =====================================
# === UTILIDAD GENERAL PARA JSON ===
# =====================================

@register.filter
def pretty_json(value):
    """Devuelve JSON con indentación."""
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        return mark_safe(f"<pre>{json.dumps(parsed, indent=2, ensure_ascii=False)}</pre>")
    except Exception:
        return value

