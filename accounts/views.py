from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import PermissionDenied


from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    UserPassesTestMixin,
)
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DeleteView,
    FormView,
    TemplateView,
)
from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView

from .forms import (
    UserForm,
    UserSearchForm,
    UserCreateForm,
    UserSetPasswordForm,
    ProfileForm,
    UserUpdateForm,
)

# ==============================================================
# === Helpers para roles
# ==============================================================

SUPERADMIN_GROUP = "superadmin"
ADMIN_GROUP = "admin"


def is_superadmin(user):
    return (
        user.is_authenticated
        and user.groups.filter(name=SUPERADMIN_GROUP).exists()
    )


def is_admin(user):
    return (
        user.is_authenticated
        and user.groups.filter(name=ADMIN_GROUP).exists()
    )


# ==============================================================
# === Vistas de perfil
# ==============================================================

class RolesInfoView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/roles_info.html"


@login_required
def profile_detail(request):
    return render(request, "accounts/profile_detail.html")


@login_required
def profile(request):
    return render(request, "accounts/profile.html")


@login_required
def profile_edit(request):
    user = request.user
    if request.method == "POST":
        uform = UserForm(request.POST, instance=user)
        pform = ProfileForm(request.POST, request.FILES, instance=user.profile)
        if uform.is_valid() and pform.is_valid():
            uform.save()
            pform.save()
            messages.success(request, "Perfil actualizado correctamente.")
            return redirect("profile")
        messages.error(request, "Revisa los campos, hay errores en el formulario.")
    else:
        uform = UserForm(instance=user)
        pform = ProfileForm(instance=user.profile)

    return render(
        request,
        "accounts/profile_edit.html",
        {"uform": uform, "pform": pform},
    )



class ChangePasswordView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        user = form.save()  # guarda la nueva contraseña
        update_session_auth_hash(self.request, user)  # mantiene sesión activa

        # 🔹 limpiar el flag de cambio obligatorio
        if hasattr(user, "profile") and getattr(user.profile, "must_change_password", False):
            user.profile.must_change_password = False
            user.profile.save()
        elif hasattr(user, "must_change_password") and user.must_change_password:
            user.must_change_password = False
            user.save()

        # 🔹 mostrar un solo mensaje
        messages.success(self.request, "Tu contraseña se cambió correctamente.")
        return redirect("accounts:profile")



class ChangePasswordDoneView(PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"


# ==============================================================
# === Mixin general para acceso de admin/superadmin
# ==============================================================

class SuperadminOrAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Solo usuarios en grupo admin o superadmin"""
    def test_func(self):
        u = self.request.user
        return is_superadmin(u) or is_admin(u)


# ==============================================================
# === Gestión de usuarios
# ==============================================================

class UserListView(SuperadminOrAdminRequiredMixin, ListView):
    model = User
    template_name = "accounts/list.html"
    context_object_name = "users"
    paginate_by = 10

    def get_queryset(self):
        qs = (
            User.objects.all()
            .order_by("username")
            .prefetch_related("groups")
        )

        # 🔹 Excluir usuarios internos del sistema
        qs = qs.exclude(is_staff=True).exclude(is_superuser=True)

        q = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()

        if q:
            qs = qs.filter(
                Q(username__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
            )

        if status == "1":
            qs = qs.filter(is_active=True)
        elif status == "0":
            qs = qs.filter(is_active=False)

        # 🔹 No mostrar al usuario actual
        qs = qs.exclude(id=self.request.user.id)

        # 🔹 Reglas por grupo
        if is_superadmin(self.request.user):
            return qs
        elif is_admin(self.request.user):
            return qs.exclude(groups__name=SUPERADMIN_GROUP).distinct()

        return qs.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = UserSearchForm(self.request.GET or None)
        return ctx


class UserCreateView(SuperadminOrAdminRequiredMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = "accounts/form.html"
    success_url = reverse_lazy("accounts:list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Si el usuario actual no es superadmin, ocultar el grupo "Superadmin"
        if not is_superadmin(self.request.user):
            if "groups" in form.fields:
                form.fields["groups"].queryset = (
                    form.fields["groups"].queryset.exclude(name=SUPERADMIN_GROUP)
                )
        return form

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.object

        # 🚩 Forzar cambio de contraseña en primer login
        if hasattr(user, "profile"):
            user.profile.must_change_password = True
            user.profile.save()
        else:
            # Si lo tienes directo en el modelo User
            if hasattr(user, "must_change_password"):
                user.must_change_password = True
                user.save()

        messages.success(self.request, "Usuario creado correctamente. Deberá cambiar su contraseña al iniciar sesión por primera vez.")
        return response


class UserUpdateView(SuperadminOrAdminRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "accounts/form.html"
    success_url = reverse_lazy("accounts:list")

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        # Si el objetivo es superadmin y el usuario no lo es → prohibido
        if obj.groups.filter(name=SUPERADMIN_GROUP).exists() and not is_superadmin(request.user):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("No tienes permisos para acceder a esta sección.")

        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if not is_superadmin(self.request.user):
            if "groups" in form.fields:
                form.fields["groups"].queryset = (
                    form.fields["groups"].queryset.exclude(name=SUPERADMIN_GROUP)
                )
        return form

    def form_valid(self, form):
        messages.success(self.request, "Usuario actualizado correctamente.")
        return super().form_valid(form)

class UserPasswordSetView(SuperadminOrAdminRequiredMixin, FormView):
    template_name = "accounts/password.html"
    form_class = UserSetPasswordForm
    success_url = reverse_lazy("accounts:list")

    def dispatch(self, request, *args, **kwargs):
        self.user_obj = User.objects.get(pk=kwargs["pk"])

        # Solo superadmin puede cambiar contraseña de superadmins
        if self.user_obj.groups.filter(name=SUPERADMIN_GROUP).exists() and not is_superadmin(request.user):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("No tienes permisos para acceder a esta sección.")


        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.user_obj
        return kwargs

    def form_valid(self, form):
        form.save()

        # obligar al usuario destino a cambiarla
        if hasattr(self.user_obj, "profile"):
            self.user_obj.profile.must_change_password = True
            self.user_obj.profile.save()
        else:
            if hasattr(self.user_obj, "must_change_password"):
                self.user_obj.must_change_password = True
                self.user_obj.save()

        if self.request.user.pk == self.user_obj.pk:
            update_session_auth_hash(self.request, self.user_obj)

        messages.success(self.request, "Contraseña actualizada correctamente. El usuario deberá cambiar su contraseña al iniciar sesión.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object"] = self.user_obj
        return ctx
