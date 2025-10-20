# accounts/templatetags/roles.py
from django import template

register = template.Library()

@register.filter
def has_group(user, group_name: str) -> bool:
    return user.is_authenticated and user.groups.filter(name=group_name).exists()

@register.filter
def has_any_group(user, groups_csv: str) -> bool:
    if not user.is_authenticated:
        return False
    names = [g.strip() for g in groups_csv.split(",") if g.strip()]
    return user.groups.filter(name__in=names).exists()

@register.filter
def has_perm(user, perm_codename: str) -> bool:
    # Ej: "trips.add_trip" o "trips.view_trip"
    return user.is_authenticated and user.has_perm(perm_codename)