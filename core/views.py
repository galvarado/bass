from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

@login_required
def post_login_redirect(request):
    u = request.user

    # Operador -> Mis viajes
    if u.groups.filter(name="operador").exists() and not (u.is_staff or u.is_superuser):
        return redirect("trips:my_list")

    # Resto -> Dashboard
    return redirect("dashboard")


@login_required
def dashboard(request):
    # Evitar que operador entre al dashboard por URL directa
    u = request.user
    if u.groups.filter(name="operador").exists() and not (u.is_staff or u.is_superuser):
        return redirect("trips:my_list")

    return render(request, "dashboard.html")
