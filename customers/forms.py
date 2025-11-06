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
            # Dirección (igual patrón que operadores)
            "calle", "no_ext", "colonia", "colonia_sat",
            "municipio", "estado", "pais", "cp", "telefono", "poblacion",
            # Crédito / facturación
            "limite_credito", "dias_credito", "forma_pago", "cuenta",
            "uso_cfdi",
            # Otros
            "observaciones",
        ]
        widgets = {
            # Dirección
            "cp": forms.TextInput(attrs={"maxlength": 5, "pattern": r"\d{5}"}),
            "estado": forms.TextInput(attrs={"readonly": "readonly"}),
            "municipio": forms.TextInput(attrs={"readonly": "readonly"}),
            "poblacion": forms.TextInput(attrs={"readonly": "readonly"}),
            "colonia": forms.Select(),
            "colonia_sat": forms.TextInput(attrs={"readonly": "readonly"}),
            "pais": forms.TextInput(attrs={"readonly": "readonly"}),
            # Campos largos
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Estilo compacto y consistente
        for name, field in self.fields.items():
            cls = "form-control form-control-sm"
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                field.widget.attrs.update({"class": cls})

        # Pre-cargar colonias si hay CP al editar
        cp = (self.instance.cp or "").strip() if getattr(self.instance, "pk", None) else ""
        if cp.isdigit() and len(cp) == 5:
            colonias = list(
                PC.objects.filter(d_codigo=cp)
                .values_list("d_asenta", flat=True).distinct().order_by("d_asenta")
            )
            self.fields["colonia"].choices = [("", "Seleccione una colonia")] + [(c, c) for c in colonias]
        else:
            self.fields["colonia"].choices = [("", "Seleccione una colonia")]

    # --- Normalización de texto ---
    def clean_nombre(self):
        return self.cleaned_data["nombre"].strip().title()

    def clean_razon_social(self):
        v = self.cleaned_data.get("razon_social")
        return v.strip().upper() if v else v

    def clean_rfc(self):
        v = (self.cleaned_data.get("rfc") or "").strip().upper()
        if not v:
            return v
        # RFC PF (13) o PM (12). Validación básica, puedes sustituir por un validador SAT si ya lo tienes.
        patron = re.compile(r"^([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,3})$")
        if not patron.match(v):
            raise forms.ValidationError("RFC inválido.")
        return v

    # --- Validaciones numéricas básicas ---
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

    # --- Coherencia CP/Colonia y autocompletar municipio/poblacion/colonia_sat ---
    def clean(self):
        cleaned = super().clean()
        cp = (cleaned.get("cp") or "").strip()
        colonia = (cleaned.get("colonia") or "").strip()

        if cp and colonia:
            if not PC.objects.filter(d_codigo=cp, d_asenta=colonia).exists():
                self.add_error("colonia", "La colonia no corresponde al código postal ingresado.")

        # Autorellenar con datos del catálogo si tenemos CP válido
        if cp.isdigit() and len(cp) == 5:
            # municipio → d_mnpio (o ciudad si no hay municipio)
            if not cleaned.get("municipio"):
                mun = (
                    PC.objects.filter(d_codigo=cp)
                    .exclude(d_mnpio__isnull=True).exclude(d_mnpio="")
                    .values_list("d_mnpio", flat=True).order_by("d_mnpio").first()
                )
                if not mun:
                    mun = (
                        PC.objects.filter(d_codigo=cp)
                        .exclude(d_ciudad__isnull=True).exclude(d_ciudad="")
                        .values_list("d_ciudad", flat=True).order_by("d_ciudad").first()
                    )
                if mun:
                    cleaned["municipio"] = mun
                    self.data = self.data.copy(); self.data["municipio"] = mun

            # población → d_ciudad
            if not cleaned.get("poblacion"):
                ciu = (
                    PC.objects.filter(d_codigo=cp)
                    .exclude(d_ciudad__isnull=True).exclude(d_ciudad=""
                ).values_list("d_ciudad", flat=True).order_by("d_ciudad").first()
                )
                if ciu:
                    cleaned["poblacion"] = ciu
                    self.data = self.data.copy(); self.data["poblacion"] = ciu

            # colonia_sat → d_tipo_asenta o asentamiento SAT (si tu modelo requiere esto)
            if not cleaned.get("colonia_sat") and colonia:
                tipo = (
                    PC.objects.filter(d_codigo=cp, d_asenta=colonia)
                    .exclude(d_tipo_asenta__isnull=True).exclude(d_tipo_asenta="")
                    .values_list("d_tipo_asenta", flat=True).order_by("d_tipo_asenta").first()
                )
                if tipo:
                    cleaned["colonia_sat"] = tipo
                    self.data = self.data.copy(); self.data["colonia_sat"] = tipo

            # país por default (solo por consistencia visual; en BD ya default='México')
            if not cleaned.get("pais"):
                cleaned["pais"] = "México"
                self.data = self.data.copy(); self.data["pais"] = "México"

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
