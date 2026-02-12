# common/mixins.py
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from trips.models import CartaPorteCFDI
from django.db.models import QuerySet


# ============================================================
# Constantes de roles
# ============================================================

GOV_GROUPS = ("superadmin", "admin")


# ============================================================
# Helpers
# ============================================================

def has_any_group(user, *groups):
    return user.is_authenticated and user.groups.filter(name__in=groups).exists()


def is_admin(user):
    return has_any_group(user, *GOV_GROUPS)


def is_superadmin(user):
    return has_any_group(user, "superadmin")


# ============================================================
# Mixins base
# ============================================================

class GroupRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Requiere pertenecer a alguno de los grupos indicados en `required_groups`.
    Admin y Superadmin siempre pasan.
    """
    required_groups = tuple()

    def test_func(self):
        u = self.request.user

        # Gobierno del sistema siempre autorizado
        if is_admin(u):
            return True

        return u.groups.filter(name__in=self.required_groups).exists()

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("No tienes permisos para acceder a esta sección.")
        return super().handle_no_permission()


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Solo admin o superadmin."""
    def test_func(self):
        return is_admin(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("Solo Admin o Superadmin pueden acceder aquí.")
        return super().handle_no_permission()


class SuperadminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Solo superadmin."""
    def test_func(self):
        return is_superadmin(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("Solo Superadmin puede acceder aquí.")
        return super().handle_no_permission()


# ============================================================
# Mixins por dominio funcional
# (estos SON los que se usan en las apps)
# ============================================================

class CatalogosRequiredMixin(GroupRequiredMixin):
    required_groups = ("catalogos",)


class OperacionRequiredMixin(GroupRequiredMixin):
    required_groups = ("operacion",)


class TallerRequiredMixin(GroupRequiredMixin):
    required_groups = ("taller",)


class AlmacenRequiredMixin(GroupRequiredMixin):
    required_groups = ("almacen",)


class FinanzasRequiredMixin(GroupRequiredMixin):
    required_groups = ("finanzas",)


class CumplimientoRequiredMixin(GroupRequiredMixin):
    required_groups = ("cumplimiento",)


class OperadorRequiredMixin(GroupRequiredMixin):
    required_groups = ("operador",)


# ============================================================
# Casos especiales
# ============================================================


class OnlyMyTripsMixin:
    """
    Restringe Trip queryset a los viajes del operador logueado.
    Usa Operator.user (OneToOneField con related_name='operator_profile')
    """

    def get_operator(self):
        user = self.request.user
        return getattr(user, "operator_profile", None)

    def get_queryset(self) -> QuerySet:
        qs = super().get_queryset()

        operator = self.get_operator()
        if not operator:
            # Seguridad total: si no es operador, no ve nada
            return qs.none()

        return qs.filter(operator=operator)
class LockIfStampedMixin:
    def dispatch(self, request, *args, **kwargs):
        trip = self.get_object()

        locked = CartaPorteCFDI.objects.filter(trip=trip, status="stamped").exists()
        if locked:
            messages.error(request, "No puedes editar o eliminar el viaje porque la Carta Porte ya fue timbrada.")
            return redirect(reverse("trips:detail", kwargs={"pk": trip.pk}))

        return super().dispatch(request, *args, **kwargs)