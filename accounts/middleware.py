# accounts/middleware.py
from django.shortcuts import redirect
from django.urls import reverse, resolve, NoReverseMatch

class ForcePasswordChangeMiddleware:
    """
    Si el usuario tiene must_change_password=True (en Profile o en User),
    lo manda a la página de cambio de contraseña y solo le deja ver unas
    cuantas URLs hasta que cambie.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        # Tiene que estar logueado
        if not user.is_authenticated:
            return self.get_response(request)

        # 1) Leer el flag, primero del profile y luego del user
        if hasattr(user, "profile"):
            must_change = getattr(user.profile, "must_change_password", False)
        else:
            must_change = getattr(user, "must_change_password", False)

        # Si no tiene que cambiar, seguimos normal
        if not must_change:
            return self.get_response(request)

        # 2) Rutas que SÍ dejamos pasar
        #    - cambio de contraseña
        #    - logout / login (para que no se quede atrapado)
        #    - admin (opcional, puedes quitarlo)
        allowed_names = {
            "accounts:password_change",
            "accounts:password_change_done",
            "login",
            "logout",
            "admin:logout",
        }

        # intenta resolver la vista actual
        try:
            match = resolve(request.path_info)
            current_name = match.view_name  # p.ej. 'accounts:password_change'
        except Exception:
            current_name = None

        # si es una de las vistas permitidas, pasa
        if current_name in allowed_names:
            return self.get_response(request)

        # opcional: deja pasar admin
        if request.path_info.startswith("/admin/"):
            # si NO quieres dejar pasar admin, quita este bloque
            return self.get_response(request)

        # 3) Si llegó aquí, debe ir a cambiar password
        # intentamos la de accounts primero
        for target in ("accounts:password_change", "password_change"):
            try:
                return redirect(target)
            except NoReverseMatch:
                continue

        # fallback final
        return redirect("/")
