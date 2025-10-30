# audit/auth_signals.py
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .models import AuditLog
from .middleware import get_current_request


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    AuditLog.objects.create(
        user=user,
        action="login",
        ip=request.META.get("REMOTE_ADDR"),
        path=request.path,
        method=request.method,
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        # aquí lo ponemos legible para la tabla
        summary=f"Inicio de sesión de {user.get_username()}",
        target=user.get_username(),   # opcional: así no sale '—'
        tags={"module": "auth"},
    )


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    # ojo: en logout a veces request viene en None
    ip = request.META.get("REMOTE_ADDR") if request else None
    path = getattr(request, "path", "")
    method = getattr(request, "method", "")
    ua = (getattr(request, "META", {}) or {}).get("HTTP_USER_AGENT", "") if request else ""

    AuditLog.objects.create(
        user=user,
        action="logout",
        ip=ip,
        path=path,
        method=method,
        user_agent=ua,
        summary=f"Cierre de sesión de {user.get_username()}",
        target=user.get_username(),   # opcional
        tags={"module": "auth"},
    )
