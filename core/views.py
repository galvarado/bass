from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.generic import TemplateView
from common.mixins import LoginRequiredMixin, SuperadminRequiredMixin


@login_required
def post_login_redirect(request):
    u = request.user

    # Operador -> Mis viajes
    if u.groups.filter(name="operador").exists() and not (u.is_staff or u.is_superuser):
        return redirect("trips:my_list")

    # Superadmin/Admin -> Dashboard financiero
    if u.is_superuser or u.is_staff:
        return redirect("finance")

    # Resto -> Dashboard operativo
    return redirect("ops")


# 🔵 Dashboard Operativo (sin finanzas)
class OpsDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/ops.html"


# 🔴 Dashboard Financiero (solo superadmin/admin)
class FinanceDashboardView(SuperadminRequiredMixin, TemplateView):
    template_name = "dashboard/finance.html"
