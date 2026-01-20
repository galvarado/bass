# suppliers/forms.py
from django import forms
from .models import Supplier

from django_postalcodes_mexico.models import PostalCode as PC
import re


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = [
            # Datos generales
            "status",
            "nombre", "razon_social",
            # Contacto
            "contacto", "telefono", "email",
            # Dirección
            "calle", "no_ext", "colonia", "colonia_sat",
            "municipio", "estado", "pais", "cp", "poblacion",
            # Pago / cuenta
            "cuenta",
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
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Estilo compacto y consistente (igual que ClientForm)
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
                .values_list("d_asenta", flat=True)
                .distinct()
                .order_by("d_asenta")
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

        if cp and colonia:
            if not PC.objects.filter(d_codigo=cp, d_asenta=colonia).exists():
                self.add_error("colonia", "La colonia no corresponde al código postal ingresado.")

        if cp.isdigit() and len(cp) == 5:
            # municipio → D_mnpio (fallback a ciudad)
            if not cleaned.get("municipio"):
                mun = (
                    PC.objects.filter(d_codigo=cp)
                    .exclude(d_mnpio__isnull=True).exclude(D_mnpio="")
                    .values_list("D_mnpio", flat=True).order_by("D_mnpio").first()
                )
                if not mun:
                    mun = (
                        PC.objects.filter(d_codigo=cp)
                        .exclude(d_ciudad__isnull=True).exclude(d_ciudad="")
                        .values_list("d_ciudad", flat=True).order_by("d_ciudad").first()
                    )
                if mun:
                    cleaned["municipio"] = mun
                    self.data = self.data.copy()
                    self.data["municipio"] = mun

            # población → d_ciudad
            if not cleaned.get("poblacion"):
                ciu = (
                    PC.objects.filter(d_codigo=cp)
                    .exclude(d_ciudad__isnull=True).exclude(d_ciudad="")
                    .values_list("d_ciudad", flat=True).order_by("d_ciudad").first()
                )
                if ciu:
                    cleaned["poblacion"] = ciu
                    self.data = self.data.copy()
                    self.data["poblacion"] = ciu

            # colonia_sat → d_tipo_asenta
            if not cleaned.get("colonia_sat") and colonia:
                tipo = (
                    PC.objects.filter(d_codigo=cp, d_asenta=colonia)
                    .exclude(d_tipo_asenta__isnull=True).exclude(d_tipo_asenta="")
                    .values_list("d_tipo_asenta", flat=True).order_by("d_tipo_asenta").first()
                )
                if tipo:
                    cleaned["colonia_sat"] = tipo
                    self.data = self.data.copy()
                    self.data["colonia_sat"] = tipo

            # país (consistencia visual)
            if not cleaned.get("pais"):
                cleaned["pais"] = "México"
                self.data = self.data.copy()
                self.data["pais"] = "México"

        return cleaned


class SupplierSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={
            "placeholder": "Nombre/razón social, teléfono o cuenta",
            "class": "form-control form-control-sm",
        }),
    )
    status = forms.ChoiceField(
        required=False,
        label="Estado",
        choices=(("", "Todos"), ("ALTA", "Alta"), ("BAJA", "Baja")),
        widget=forms.Select(attrs={"class": "form-control form-control-sm"}),
    )
