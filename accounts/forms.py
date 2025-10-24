from django import forms
from django.contrib.auth.models import User, Group
from .models import Profile
from django.contrib.auth import get_user_model
from django import forms
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from django.contrib.auth.models import User


User = get_user_model()

STATUS_CHOICES = (
    ("", "Todos"),
    ("active", "Activos"),
    ("inactive", "Inactivos"),
)

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["phone", "rfc", "curp", "photo"]
        widgets = {
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "rfc": forms.TextInput(attrs={"class": "form-control", "maxlength": 13}),
            "curp": forms.TextInput(attrs={"class": "form-control", "maxlength": 18}),
        }





class UserSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Buscar usuario/nombre/email"})
    )
    status = forms.ChoiceField(
        required=False,
        choices=(("", "Todos"), ("1", "Activos"), ("0", "Inactivos")),
        widget=forms.Select(attrs={"class": "form-control"})
    )

class UserCreateForm(UserCreationForm):
    first_name = forms.CharField(required=False, widget=forms.TextInput(attrs={"class":"form-control"}))
    last_name  = forms.CharField(required=False, widget=forms.TextInput(attrs={"class":"form-control"}))
    email      = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"class":"form-control"}))
    is_active  = forms.BooleanField(required=False, initial=True)
    is_staff   = forms.BooleanField(required=False, initial=False)

    # ⬇️ NUEVO: seleccionar uno o varios grupos
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all().order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username","first_name","last_name","email","is_active","is_staff","groups")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class":"form-control"})
        self.fields["password1"].widget.attrs.update({"class":"form-control"})
        self.fields["password2"].widget.attrs.update({"class":"form-control"})

    def save(self, commit=True):
        user = super().save(commit=commit)
        # asigna grupos después de crear
        if commit:
            user.groups.set(self.cleaned_data.get("groups", []))
        else:
            # si no se hace commit, guarda para que la vista haga user.save() y luego set()
            self._pending_groups = self.cleaned_data.get("groups", [])
        return user


class UserUpdateForm(forms.ModelForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all().order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = User
        fields = ("username","first_name","last_name","email","is_active","is_staff","groups")
        widgets = {
            "username": forms.TextInput(attrs={"class":"form-control"}),
            "first_name": forms.TextInput(attrs={"class":"form-control"}),
            "last_name": forms.TextInput(attrs={"class":"form-control"}),
            "email": forms.EmailInput(attrs={"class":"form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # inicializa grupos actuales del usuario
        if self.instance and self.instance.pk:
            self.fields["groups"].initial = self.instance.groups.all()

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            user.groups.set(self.cleaned_data.get("groups", []))
        return user

class UserSetPasswordForm(SetPasswordForm):
    # Just for parity if you want to inject CSS classes
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields["new_password1"].widget.attrs.update({"class":"form-control"})
        self.fields["new_password2"].widget.attrs.update({"class":"form-control"})
