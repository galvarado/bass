# common/mixins.py
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

# Si ya tienes esto, úsalo; si no, lo reemplazamos por helpers de grupo
from .permissions import is_superadmin  # existente en tu proyecto


GOV_GROUPS = ("superadmin", "admin")


def has_any_group(user, *groups):
    return user.is_authenticated and user.groups.filter(name__in=groups).exists()


def is_admin(user):
    return has_any_group(user, *GOV_GROUPS)


# -------------------------------------------------------------------
# Mixins base
# -------------------------------------------------------------------

class SuperadminRequiredMixin(LoginRequiredMixin):
    """
    Solo superadmin (por grupo), no por is_staff/is_superuser.
    """
    def dispatch(self, request, *args, **kwargs):
        if not is_superadmin(request.user) and not has_any_group(request.user, "superadmin"):
            raise PermissionDenied("No tienes permisos para acceder a esta sección.")
  # 403
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Solo admin o superadmin (por grupos).
    """
    def test_func(self):
        return is_admin(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("No tienes permisos para acceder a esta sección.")
        return super().handle_no_permission()


class GroupRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Permite acceso si el usuario pertenece a alguno de required_groups.
    Admin/Superadmin siempre pasan.
    """
    required_groups = tuple()

    def test_func(self):
        u = self.request.user

        if is_admin(u):
            return True

        return u.groups.filter(name__in=self.required_groups).exists()

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("No tienes permisos para acceder a esta sección.")
        return super().handle_no_permission()


# -------------------------------------------------------------------
# Casos específicos
# -------------------------------------------------------------------

class OperatorOnlyMixin(GroupRequiredMixin):
    """
    Operador (y admin/superadmin por override del GroupRequiredMixin).
    """
    required_groups = ("operador",)


class OnlyMyTripsMixin:
    """
    Restringe el queryset de Trip a los viajes del operador logueado.
    Admin/Superadmin ven todo.
    """
    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user

        if is_admin(u) or has_any_group(u, "superadmin"):
            return qs

        # Operador: solo sus viajes
        return qs.filter(operator__user=u)
