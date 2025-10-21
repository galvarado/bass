# operators/forms.py
from django import forms
from django.utils import timezone
from .models import Operator

class OperatorForm(forms.ModelForm):
    class Meta:
        model = Operator
        fields = [
            "first_name", "last_name_paterno", "last_name_materno",
            "rfc", "license_number", "license_expires_at",
            "phone", "email", "active",
        ]
        widgets = {
            "license_expires_at": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            elif not isinstance(field.widget, forms.DateInput):
                field.widget.attrs.update({"class": "form-control"})
        self.fields["license_expires_at"].widget.attrs.update({"class": "form-control"})
        self.fields["license_expires_at"].input_formats = ["%Y-%m-%d"]

    def clean_license_expires_at(self):
        v = self.cleaned_data["license_expires_at"]
        if v:  # permite vacío si decides hacerlo opcional algún día
            if v < timezone.now().date():
                raise forms.ValidationError("La vigencia de la licencia no puede estar en el pasado.")
        return v

    def clean_first_name(self):
        return self.cleaned_data["first_name"].strip().title()

    def clean_last_name_paterno(self):
        return self.cleaned_data["last_name_paterno"].strip().title()

    def clean_last_name_materno(self):
        return self.cleaned_data["last_name_materno"].strip().title()


# 🔎 Formulario de búsqueda para la vista de lista
class OperatorSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={
            "placeholder": "Nombre, apellidos, RFC, licencia, email o teléfono",
            "class": "form-control",
        }),
    )
    status = forms.ChoiceField(
        required=False,
        label="Estado",
        choices=(("", "Todos"), ("1", "Activos"), ("0", "Inactivos")),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
