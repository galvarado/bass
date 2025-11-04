# operators/forms.py
from django import forms
from django.utils import timezone
from .models import Operator


class OperatorForm(forms.ModelForm):
    class Meta:
        model = Operator
        fields = [
            # Datos personales
            "nombre", "rfc", "curp", "tipo_sangre", "imss",
            "fecha_nacimiento", "fecha_ingreso", "puesto",

            # Dirección
            "calle", "no_ext", "colonia", "colonia_sat",
            "municipio", "estado", "pais", "cp", "telefono",

            # Contrato y régimen
            "tipo_contrato", "tipo_regimen", "tipo_jornada",
            "tipo_liquidacion", "periodicidad", "cuenta_bancaria", "cuenta",
            "poblacion",

            # Sueldos y topes
            "sueldo_fijo", "comision", "tope",

            # Documentos
            "ine", "ine_vencimiento",
            "licencia_federal", "licencia_federal_vencimiento",
            "visa", "visa_vencimiento",
            "pasaporte", "pasaporte_vencimiento",
            "examen_medico", "examen_medico_vencimiento",
            "rcontrol", "rcontrol_vencimiento",
            "antidoping", "antidoping_vencimiento",

            # Control
            "status", 
        ]

        widgets = {
            # Fechas
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_ingreso": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "ine_vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "licencia_federal_vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "visa_vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "pasaporte_vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "examen_medico_vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "rcontrol_vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "antidoping_vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    # ---- Inicialización de estilos ----
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({"class": "form-control form-control-sm"})
            elif isinstance(field.widget, forms.DateInput):
                field.widget.attrs.update({"class": "form-control form-control-sm"})
            else:
                field.widget.attrs.update({"class": "form-control form-control-sm"})

        # Define formato de fecha en todos los campos tipo date
        for f in self.fields:
            if isinstance(self.fields[f].widget, forms.DateInput):
                self.fields[f].input_formats = ["%Y-%m-%d"]

    # ---- Validaciones ----
    def _check_future_or_present(self, field_name):
        v = self.cleaned_data.get(field_name)
        if v and v < timezone.now().date():
            raise forms.ValidationError("La fecha de vencimiento no puede estar en el pasado.")
        return v

    def clean_ine_vencimiento(self): return self._check_future_or_present("ine_vencimiento")
    def clean_licencia_federal_vencimiento(self): return self._check_future_or_present("licencia_federal_vencimiento")
    def clean_visa_vencimiento(self): return self._check_future_or_present("visa_vencimiento")
    def clean_pasaporte_vencimiento(self): return self._check_future_or_present("pasaporte_vencimiento")
    def clean_examen_medico_vencimiento(self): return self._check_future_or_present("examen_medico_vencimiento")
    def clean_rcontrol_vencimiento(self): return self._check_future_or_present("rcontrol_vencimiento")
    def clean_antidoping_vencimiento(self): return self._check_future_or_present("antidoping_vencimiento")

    # ---- Normalización de texto ----
    def clean_nombre(self):
        return self.cleaned_data["nombre"].strip().title()

    def clean_puesto(self):
        value = self.cleaned_data.get("puesto")
        return value.strip().title() if value else value


# 🔎 Formulario de búsqueda
class OperatorSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={
            "placeholder": "Nombre, RFC, CURP, licencia, teléfono o puesto",
            "class": "form-control form-control-sm",
        }),
    )
    status = forms.ChoiceField(
        required=False,
        label="Estado",
        choices=(("", "Todos"), ("1", "Activos"), ("0", "Inactivos")),
        widget=forms.Select(attrs={"class": "form-control form-control-sm"}),
    )
