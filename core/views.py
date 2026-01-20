from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.generic import TemplateView
from common.mixins import AdminRequiredMixin

@login_required
def post_login_redirect(request):
    u = request.user

    # Operador -> Mis viajes
    if u.groups.filter(name="operador").exists() and not (u.is_staff or u.is_superuser):
        return redirect("trips:my_list")

    # Resto -> Dashboard
    return redirect("dashboard")

class DashboardView(AdminRequiredMixin, TemplateView):
    template_name = "dashboard.html"