# locations/forms.py
from django import forms
from .models import Location

from django_postalcodes_mexico.models import PostalCode as PC  # mismo helper
import re


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = [
            "client", "nombre",
            # Dirección
            "calle", "no_ext", "colonia", "colonia_sat",
            "municipio", "estado", "pais", "cp", "poblacion",
            # Contacto
            "contacto", "telefono", "email",
            # Otros
            "referencias", "horario",
        ]
        widgets = {
            # Dirección
            "cp": forms.TextInput(attrs={"maxlength": 5, "pattern": r"\d{5}"}),
            "estado": forms.TextInput(attrs={"readonly": "readonly"}),
            "municipio": forms.TextInput(attrs={"readonly": "readonly"}),
            "poblacion": forms.TextInput(attrs={"readonly": "readonly"}),
            "colonia": forms.Select(),  # se llena dinámicamente por CP
            "colonia_sat": forms.TextInput(attrs={"readonly": "readonly"}),
            "pais": forms.TextInput(attrs={"readonly": "readonly"}),
            # Otros
            "referencias": forms.Textarea(attrs={"rows": 3}),
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

    def clean_contacto(self):
        v = self.cleaned_data.get("contacto")
        return v.strip().title() if v else v

    def clean_email(self):
        v = self.cleaned_data.get("email")
        return v.strip().lower() if v else v

    # --- Coherencia CP/Colonia y autocompletar municipio/poblacion/colonia_sat ---
    def clean(self):
        cleaned = super().clean()
        cp = (cleaned.get("cp") or "").strip()
        colonia = (cleaned.get("colonia") or "").strip()

        # Validación básica de CP (opcional, ya hay pattern en widget)
        if cp and not re.fullmatch(r"\d{5}", cp):
            self.add_error("cp", "El código postal debe tener 5 dígitos.")

        # Validar relación CP-colonia
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
                    .exclude(d_ciudad__isnull=True).exclude(d_ciudad="")
                    .values_list("d_ciudad", flat=True).order_by("d_ciudad").first()
                )
                if ciu:
                    cleaned["poblacion"] = ciu
                    self.data = self.data.copy(); self.data["poblacion"] = ciu

            # colonia_sat → d_tipo_asenta (si hay colonia)
            if not cleaned.get("colonia_sat") and colonia:
                tipo = (
                    PC.objects.filter(d_codigo=cp, d_asenta=colonia)
                    .exclude(d_tipo_asenta__isnull=True).exclude(d_tipo_asenta="")
                    .values_list("d_tipo_asenta", flat=True).order_by("d_tipo_asenta").first()
                )
                if tipo:
                    cleaned["colonia_sat"] = tipo
                    self.data = self.data.copy(); self.data["colonia_sat"] = tipo

            # país por default (por consistencia visual)
            if not cleaned.get("pais"):
                cleaned["pais"] = "México"
                self.data = self.data.copy(); self.data["pais"] = "México"

        return cleaned


class LocationSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Buscar por nombre",
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-sm",
            "placeholder": "Nombre de ubicación…"
        })
    )
    show_deleted = forms.BooleanField(required=False, widget=forms.HiddenInput)
    show_all = forms.BooleanField(required=False, widget=forms.HiddenInput)
