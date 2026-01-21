# clients/forms.py
from django import forms
from django.utils import timezone
from .models import Client

from django_postalcodes_mexico.models import PostalCode as PC  # mismo helper que en operadores
import re


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            # Datos generales
            "status",
            "nombre", "razon_social", "rfc", "regimen_fiscal", "id_tributario",
            # Dirección
            "calle", "no_ext", "colonia", "colonia_sat",
            "municipio", "estado", "pais", "cp", "telefono", "poblacion",
            # Crédito / facturación
            "limite_credito", "dias_credito", "forma_pago", "cuenta",
            "uso_cfdi",
            # Otros
            "observaciones",
        ]
        widgets = {
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Bootstrap
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                field.widget.attrs.update({"class": "form-control form-control-sm"})

        # País default (create)
        if not getattr(self.instance, "pk", None) and not self.is_bound:
            self.initial["pais"] = "MX"

        # Determinar país actual (POST tiene prioridad)
        if self.is_bound:
            pais = (self.data.get("pais") or "").strip() or "MX"
        else:
            pais = (getattr(self.instance, "pais", None) or "MX").strip() or "MX"

        # Configurar por país
        self._apply_country_mode(pais)

        # Precargar colonias SOLO si MX y hay CP (edición)
        cp = ""
        if not self.is_bound and getattr(self.instance, "pk", None):
            cp = (self.instance.cp or "").strip()

        if pais == "MX":
            # CP: 5 dígitos
            self.fields["cp"].widget = forms.TextInput(attrs={"maxlength": 5, "pattern": r"\d{5}"})
            self.fields["cp"].widget.attrs.update({"class": "form-control form-control-sm"})

            # colonia: select
            self.fields["colonia"].widget = forms.Select()
            self.fields["colonia"].widget.attrs.update({"class": "form-control form-control-sm"})

            # readonly derivados
            for f in ["estado", "municipio", "poblacion", "colonia_sat"]:
                self.fields[f].widget.attrs.update({"readonly": "readonly"})

            # choices colonia por CP (solo en edición si hay CP)
            if cp.isdigit() and len(cp) == 5:
                colonias = list(
                    PC.objects.filter(d_codigo=cp)
                    .values_list("d_asenta", flat=True).distinct().order_by("d_asenta")
                )
                self.fields["colonia"].choices = [("", "Seleccione una colonia")] + [(c, c) for c in colonias]
            else:
                self.fields["colonia"].choices = [("", "Seleccione una colonia")]

        else:
            # US: colonia libre
            self.fields["colonia"].widget = forms.TextInput()
            self.fields["colonia"].widget.attrs.update({"class": "form-control form-control-sm"})

            # US: estado/municipio/poblacion editables
            for f in ["estado", "municipio", "poblacion"]:
                self.fields[f].widget.attrs.pop("readonly", None)

            # US: CP libre (ZIP puede llevar guión)
            self.fields["cp"].disabled = False
            self.fields["cp"].widget = forms.TextInput(attrs={"maxlength": 10})
            self.fields["cp"].widget.attrs.update({"class": "form-control form-control-sm"})
            self.fields["cp"].widget.attrs.pop("pattern", None)

            # US: colonia_sat no aplica
            self.fields["colonia_sat"].disabled = True

    def _apply_country_mode(self, pais: str):
        # hook por si luego quieres extender
        pass

    # ---------- Normalización ----------
    def clean_nombre(self):
        return (self.cleaned_data.get("nombre") or "").strip().title()

    def clean_razon_social(self):
        v = self.cleaned_data.get("razon_social")
        return v.strip().upper() if v else v

    def clean_rfc(self):
        v = (self.cleaned_data.get("rfc") or "").strip().upper()
        if not v:
            return v
        patron = re.compile(r"^([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,3})$")
        if not patron.match(v):
            raise forms.ValidationError("RFC inválido.")
        return v

    def clean_limite_credito(self):
        v = self.cleaned_data.get("limite_credito")
        if v is not None and v < 0:
            raise forms.ValidationError("El límite de crédito no puede ser negativo.")
        return v

    def clean_dias_credito(self):
        v = self.cleaned_data.get("dias_credito")
        if v is not None and v < 0:
            raise forms.ValidationError("Los días de crédito no pueden ser negativos.")
        return v

    # ---------- Validación / Autofill ----------
    def clean(self):
        cleaned = super().clean()
        pais = (cleaned.get("pais") or "MX").strip() or "MX"

        # US: NO validar CP/colonia contra catálogo MX
        if pais == "US":
            cleaned["colonia_sat"] = ""
            return cleaned

        # MX:
        cp = (cleaned.get("cp") or "").strip()
        colonia = (cleaned.get("colonia") or "").strip()

        if cp and not re.fullmatch(r"\d{5}", cp):
            self.add_error("cp", "El código postal debe tener 5 dígitos.")

        if cp and colonia:
            if not PC.objects.filter(d_codigo=cp, d_asenta=colonia).exists():
                self.add_error("colonia", "La colonia no corresponde al código postal ingresado.")

        if cp.isdigit() and len(cp) == 5:
            # municipio
            if not cleaned.get("municipio"):
                mun = (
                    PC.objects.filter(d_codigo=cp)
                    .exclude(D_mnpio__isnull=True).exclude(D_mnpio="")
                    .values_list("D_mnpio", flat=True).order_by("D_mnpio").first()
                ) or (
                    PC.objects.filter(d_codigo=cp)
                    .exclude(d_ciudad__isnull=True).exclude(d_ciudad="")
                    .values_list("d_ciudad", flat=True).order_by("d_ciudad").first()
                )
                if mun:
                    cleaned["municipio"] = mun

            # poblacion (ciudad)
            if not cleaned.get("poblacion"):
                ciu = (
                    PC.objects.filter(d_codigo=cp)
                    .exclude(d_ciudad__isnull=True).exclude(d_ciudad="")
                    .values_list("d_ciudad", flat=True).order_by("d_ciudad").first()
                )
                if ciu:
                    cleaned["poblacion"] = ciu

            # colonia_sat (tipo asentamiento)
            if not cleaned.get("colonia_sat") and colonia:
                tipo = (
                    PC.objects.filter(d_codigo=cp, d_asenta=colonia)
                    .exclude(c_tipo_asenta__isnull=True).exclude(c_tipo_asenta="")
                    .values_list("c_tipo_asenta", flat=True).order_by("c_tipo_asenta").first()
                )
                if tipo:
                    cleaned["colonia_sat"] = tipo

        return cleaned
class ClientSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={
            "placeholder": "Nombre/razón social, RFC, teléfono o cuenta",
            "class": "form-control form-control-sm",
        }),
    )
    status = forms.ChoiceField(
        required=False,
        label="Estado",
        choices=(("", "Todos"), ("1", "Activos"), ("0", "Inactivos")),
        widget=forms.Select(attrs={"class": "form-control form-control-sm"}),
    )
