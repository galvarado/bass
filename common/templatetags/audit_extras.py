from django import template
register = template.Library()

@register.filter
def action_badge(action_key):
    return {
        "create": "success",
        "update": "primary",
        "soft_delete": "danger",
        "restore": "warning",
        "login": "info",
        "logout": "secondary",
        "export": "dark",
        "import": "dark",
        "permission": "warning",
    }.get(action_key, "light")