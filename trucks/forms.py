# trucks/forms.py
from django import forms
from .models import Truck
from .models import ReeferBox

class TruckForm(forms.ModelForm):
    class Meta:
        model = Truck
        fields = [
            "placas","numero_economico","serie","marca",
            "motor","combustible","capacidad_combustible","peso_bruto",
            "categoria","rin",
            "ciclo_mtto",
            "seguro","tarjeta_circulacion",
        ]
        widgets = {
            # números
            "capacidad_combustible": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "peso_bruto": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                field.widget.attrs.update({"class": "form-control form-control-sm"})

    # --- Normalización de texto ---
    def clean_placas(self):
        v = (self.cleaned_data.get("placas") or "").strip().upper()
        return v

    def clean_numero_economico(self):
        v = (self.cleaned_data.get("numero_economico") or "").strip().upper()
        return v

    def clean_serie(self):
        v = self.cleaned_data.get("serie")
        return v.strip().upper() if v else v

    def clean_marca(self):
        v = self.cleaned_data.get("marca")
        return v.strip().title() if v else v

    # --- Validaciones numéricas ---
    def clean_capacidad_combustible(self):
        v = self.cleaned_data.get("capacidad_combustible")
        if v is not None and v < 0:
            raise forms.ValidationError("La capacidad de combustible debe ser mayor o igual a 0.")
        return v

    def clean_peso_bruto(self):
        v = self.cleaned_data.get("peso_bruto")
        if v is not None and v < 0:
            raise forms.ValidationError("El peso bruto debe ser mayor o igual a 0.")
        return v


class TruckSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={
            "placeholder": "Económico, placas, serie (VIN), marca, motor, categoría",
            "class": "form-control form-control-sm",
        }),
    )


class ReeferBoxForm(forms.ModelForm):
    class Meta:
        model = ReeferBox
        fields = [
            "categoria","numero_economico","modelo","marca","numero_serie","placas",
            "km","ciclo_mtto","rin","peso_bruto","combustible","capacidad_thermo","tipo_remolque",
            "seguro","tarjeta_circulacion",
        ]
        widgets = {
            "km": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "peso_bruto": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "capacidad_thermo": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # estilos compactos
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                field.widget.attrs.update({"class": "form-control form-control-sm"})


    # --- Normalizaciones ---
    def clean_numero_economico(self):
        v = (self.cleaned_data.get("numero_economico") or "").strip().upper()
        return v

    def clean_placas(self):
        v = self.cleaned_data.get("placas")
        return v.strip().upper() if v else v

    def clean_numero_serie(self):
        v = self.cleaned_data.get("numero_serie")
        return v.strip().upper() if v else v

    def clean_marca(self):
        v = self.cleaned_data.get("marca")
        return v.strip().title() if v else v

    # --- Validaciones numéricas ---
    def clean_km(self):
        v = self.cleaned_data.get("km")
        if v is not None and v < 0:
            raise forms.ValidationError("El kilometraje debe ser mayor o igual a 0.")
        return v

    def clean_peso_bruto(self):
        v = self.cleaned_data.get("peso_bruto")
        if v is not None and v < 0:
            raise forms.ValidationError("El peso bruto debe ser mayor o igual a 0.")
        return v

    def clean_capacidad_thermo(self):
        v = self.cleaned_data.get("capacidad_thermo")
        if v is not None and v < 0:
            raise forms.ValidationError("La capacidad del Thermo debe ser mayor o igual a 0.")
        return v

class ReeferBoxSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={
            "placeholder": "Económico, placas, serie, marca, modelo, tipo de remolque",
            "class": "form-control form-control-sm",
        }),
    )
