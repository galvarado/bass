# common/mixins.py
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .permissions import is_superadmin

class SuperadminRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not is_superadmin(request.user):
            raise PermissionDenied  # 403
        return super().dispatch(request, *args, **kwargs)
        

class OperatorOnlyMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Permite acceso a usuarios en grupo 'operador' (o staff/superuser).
    """
    operator_group_name = "operador"

    def test_func(self):
        u = self.request.user
        return u.groups.filter(name=self.operator_group_name).exists()

class OnlyMyTripsMixin:
    """
    Restringe el queryset de Trip a los viajes del operador logueado.
    Staff/superuser ven todo.
    """
    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user

        if u.is_superuser or u.is_staff:
            return qs

        return qs.filter(operator__user=u)