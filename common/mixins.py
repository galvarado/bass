# common/mixins.py
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin
from .permissions import is_superadmin

class SuperadminRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not is_superadmin(request.user):
            raise PermissionDenied  # 403
        return super().dispatch(request, *args, **kwargs)
