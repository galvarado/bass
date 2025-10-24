from django.contrib.auth.decorators import login_required
from django.shortcuts import render


from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User, Group
from django.contrib.auth import update_session_auth_hash
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, FormView
from .forms import UserForm, UserSearchForm, UserCreateForm, UserSetPasswordForm, ProfileForm, UserUpdateForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView
from django.urls import reverse_lazy
from django.shortcuts import render, redirect

@login_required
def profile_detail(request):
    # Si quieres, puedes reutilizar tu template actual para solo ver
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

    return render(request, "accounts/profile_edit.html", {
        "uform": uform,
        "pform": pform,
    })

class ChangePasswordView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("password_change_done")

class ChangePasswordDoneView(PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"

class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

class UserListView(LoginRequiredMixin, ListView):
    model = User
    template_name = "accounts/list.html"
    context_object_name = "users"
    paginate_by = 10

    def get_queryset(self):
        qs = (User.objects
            .all()
            .order_by("username")
            .prefetch_related("groups"))  # ← trae grupos en un solo query

        q = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()

        if q:
            qs = qs.filter(
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(email__icontains=q)
            )

        if status == "1":
            qs = qs.filter(is_active=True)
        elif status == "0":
            qs = qs.filter(is_active=False)

        qs = qs.exclude(is_superuser=True)
        qs = qs.exclude(id=self.request.user.id)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = UserSearchForm(self.request.GET or None)
        return ctx


class UserCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = "accounts/form.html"
    success_url = reverse_lazy("accounts:list")

    def form_valid(self, form):
        messages.success(self.request, "Usuario creado correctamente.")
        return super().form_valid(form)

class UserUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "accounts/form.html"
    success_url = reverse_lazy("accounts:list")

    def form_valid(self, form):
        messages.success(self.request, "Usuario actualizado correctamente.")
        return super().form_valid(form)

class UserDeleteView(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
    model = User
    template_name = "accounts/confirm_delete.html"
    success_url = reverse_lazy("accounts:list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Usuario eliminado.")
        return super().delete(request, *args, **kwargs)

class UserPasswordSetView(LoginRequiredMixin, StaffRequiredMixin, FormView):
    template_name = "accounts/password.html"
    form_class = UserSetPasswordForm
    success_url = reverse_lazy("accounts:list")

    def dispatch(self, request, *args, **kwargs):
        self.user_obj = User.objects.get(pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.user_obj
        return kwargs

    def form_valid(self, form):
        form.save()
        # Do not log the admin out if changing own password
        if self.request.user.pk == self.user_obj.pk:
            update_session_auth_hash(self.request, self.user_obj)
        messages.success(self.request, "Contraseña actualizada correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object"] = self.user_obj
        return ctx
