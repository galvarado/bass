# common/permissions.py
from django.contrib.auth.models import Group

SUPERADMIN_GROUP = "superadmin"
ADMIN_GROUP = "admin"

def is_superadmin(user):
    return user.is_authenticated and user.groups.filter(name=SUPERADMIN_GROUP).exists()

def is_admin(user):
    return user.is_authenticated and user.groups.filter(name=ADMIN_GROUP).exists()
