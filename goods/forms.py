# mercancias/forms.py
from django import forms
from .models import Mercancia


class MercanciaForm(forms.ModelForm):
    class Meta:
        model = Mercancia
        fields = [
            "clave",
            "nombre",
            "fraccion_arancelaria",
            "comercio_exterior_uuid",
        ]
        widgets = {
            "clave": forms.TextInput(attrs={"maxlength": 50}),
            "nombre": forms.TextInput(attrs={"maxlength": 255}),
            "fraccion_arancelaria": forms.TextInput(
                attrs={
                    "maxlength": 20,
                    # fracción arancelaria suele ser 8 dígitos; lo dejamos flexible
                    "placeholder": "Ej: 01012101",
                }
            ),
            "comercio_exterior_uuid": forms.TextInput(
                attrs={"placeholder": "UUID (opcional)"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # bootstrap (mismo patrón que OperatorForm)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                field.widget.attrs.update({"class": "form-control form-control-sm"})

    # --- Normalización de texto ---
    def clean_clave(self):
        v = (self.cleaned_data.get("clave") or "").strip()
        if not v:
            raise forms.ValidationError("La clave es obligatoria.")
        return v.upper()  # consistente para búsquedas/únicos

    def clean_nombre(self):
        v = (self.cleaned_data.get("nombre") or "").strip()
        if not v:
            raise forms.ValidationError("El nombre es obligatorio.")
        # title() puede romper siglas; preferimos solo strip
        return v

    def clean_fraccion_arancelaria(self):
        v = (self.cleaned_data.get("fraccion_arancelaria") or "").strip()
        if not v:
            return None

        # opcional: validar que sean dígitos (si quieres permitir guiones/puntos, quítalo)
        if not v.isdigit():
            raise forms.ValidationError("La fracción arancelaria debe contener solo dígitos.")
        if len(v) not in (8, 10):  # 8 común; a veces se maneja 10 (ajústalo si quieres)
            raise forms.ValidationError("La fracción arancelaria debe tener 8 o 10 dígitos.")
        return v


class MercanciaSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Clave, nombre, fracción arancelaria o UUID",
                "class": "form-control form-control-sm",
            }
        ),
    )
    status = forms.ChoiceField(
        required=False,
        label="Estado",
        choices=(("", "Todos"), ("1", "Activos"), ("0", "Eliminados")),
        widget=forms.Select(attrs={"class": "form-control form-control-sm"}),
    )
