from django.contrib.auth.decorators import login_required
from django.shortcuts import render



from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView
from django.urls import reverse_lazy
from django.shortcuts import render, redirect

from .forms import UserForm, ProfileForm

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
