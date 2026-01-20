# locations/forms.py
from django import forms
from .models import Location, Route

from django_postalcodes_mexico.models import PostalCode as PC  # mismo helper
import re



class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = [
            "client", "nombre",
            "calle", "no_ext", "colonia", "colonia_sat",
            "municipio", "estado", "pais", "cp", "poblacion",
            "contacto", "telefono", "email",
            "referencias", "horario",
        ]
        widgets = {
            "referencias": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # bootstrap
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                field.widget.attrs.update({"class": "form-control form-control-sm"})

        # cliente label
        if "client" in self.fields:
            self.fields["client"].label_from_instance = (lambda obj: obj.nombre)
            self.fields["client"].queryset = self.fields["client"].queryset.order_by("nombre")

        # país default (en create)
        if not getattr(self.instance, "pk", None) and not self.is_bound:
            self.initial["pais"] = "MX"

        # determinar país actual (POST tiene prioridad)
        pais = None
        if self.is_bound:
            pais = (self.data.get("pais") or "").strip()
        else:
            pais = (getattr(self.instance, "pais", None) or "MX").strip() or "MX"

        # configurar widgets según país
        self._apply_country_mode(pais)

        # precargar colonias SOLO si MX y hay CP
        cp = ""
        if not self.is_bound and getattr(self.instance, "pk", None):
            cp = (self.instance.cp or "").strip()

        if pais == "MX":
            # CP con patrón 5 dígitos
            self.fields["cp"].widget = forms.TextInput(attrs={"maxlength": 5, "pattern": r"\d{5}"})
            self.fields["cp"].widget.attrs.update({"class": "form-control form-control-sm"})

            # colonia como select (se llena por CP)
            self.fields["colonia"].widget = forms.Select()
            self.fields["colonia"].widget.attrs.update({"class": "form-control form-control-sm"})

            # readonly en campos derivados de CP
            for f in ["estado", "municipio", "poblacion", "colonia_sat"]:
                self.fields[f].widget.attrs.update({"readonly": "readonly"})

            # choices de colonia al editar
            if cp.isdigit() and len(cp) == 5:
                colonias = list(
                    PC.objects.filter(d_codigo=cp)
                    .values_list("d_asenta", flat=True).distinct().order_by("d_asenta")
                )
                self.fields["colonia"].choices = [("", "Seleccione una colonia")] + [(c, c) for c in colonias]
            else:
                self.fields["colonia"].choices = [("", "Seleccione una colonia")]

        else:
            # US: colonia texto libre
            self.fields["colonia"].widget = forms.TextInput()
            self.fields["colonia"].widget.attrs.update({"class": "form-control form-control-sm"})

            # US: estado/municipio/poblacion editables
            for f in ["estado", "municipio", "poblacion"]:
                self.fields[f].widget.attrs.pop("readonly", None)

            # ✅ US: CP habilitado y SIN pattern numérico (ZIP puede tener guión)
            self.fields["cp"].disabled = False
            self.fields["cp"].widget = forms.TextInput(attrs={"maxlength": 10})
            self.fields["cp"].widget.attrs.update({"class": "form-control form-control-sm"})

            # US: colonia_sat no aplica (SAT)
            self.fields["colonia_sat"].disabled = True

    def _apply_country_mode(self, pais: str):
        # nada aquí por ahora, pero te lo dejo por si quieres extender
        pass

    def clean_nombre(self):
        return self.cleaned_data["nombre"].strip().title()

    def clean_contacto(self):
        v = self.cleaned_data.get("contacto")
        return v.strip().title() if v else v

    def clean_email(self):
        v = self.cleaned_data.get("email")
        return v.strip().lower() if v else v

    def clean(self):
        cleaned = super().clean()
        pais = (cleaned.get("pais") or "MX").strip()

        # --- USA: NO validar CP / NO validar CP-colonia / NO autocompletar por catálogo ---
        if pais == "US":
            # como cp está disabled, puede no venir. Asegura que no quede basura.
            cleaned["colonia_sat"] = ""
            return cleaned

        # --- MX: tu lógica actual (con pequeñas protecciones) ---
        cp = (cleaned.get("cp") or "").strip()
        colonia = (cleaned.get("colonia") or "").strip()

        if cp and not re.fullmatch(r"\d{5}", cp):
            self.add_error("cp", "El código postal debe tener 5 dígitos.")

        if cp and colonia:
            if not PC.objects.filter(d_codigo=cp, d_asenta=colonia).exists():
                self.add_error("colonia", "La colonia no corresponde al código postal ingresado.")

        if cp.isdigit() and len(cp) == 5:
            if not cleaned.get("municipio"):
                mun = (
                    PC.objects.filter(d_codigo=cp)
                    .exclude(d_mnpio__isnull=True).exclude(D_mnpio="")
                    .values_list("D_mnpio", flat=True).order_by("D_mnpio").first()
                ) or (
                    PC.objects.filter(d_codigo=cp)
                    .exclude(d_ciudad__isnull=True).exclude(d_ciudad="")
                    .values_list("d_ciudad", flat=True).order_by("d_ciudad").first()
                )
                if mun:
                    cleaned["municipio"] = mun

            if not cleaned.get("poblacion"):
                ciu = (
                    PC.objects.filter(d_codigo=cp)
                    .exclude(d_ciudad__isnull=True).exclude(d_ciudad="")
                    .values_list("d_ciudad", flat=True).order_by("d_ciudad").first()
                )
                if ciu:
                    cleaned["poblacion"] = ciu

            if not cleaned.get("colonia_sat") and colonia:
                tipo = (
                    PC.objects.filter(d_codigo=cp, d_asenta=colonia)
                    .exclude(d_tipo_asenta__isnull=True).exclude(d_tipo_asenta="")
                    .values_list("d_tipo_asenta", flat=True).order_by("d_tipo_asenta").first()
                )
                if tipo:
                    cleaned["colonia_sat"] = tipo

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


# =========================
# FORM PARA CREAR RUTA
# =========================
class RouteForm(forms.ModelForm):
    class Meta:
        model = Route
        fields = [
            "client",
            "nombre",
            "origen",
            "destino",
            "tarifa_cliente",
            "pago_operador",
            "pago_transfer_propio",
            "pago_transfer_solo_cruce",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Estilo
        for field in self.fields.values():
            field.widget.attrs.update({
                "class": "form-control form-control-sm"
            })

        # 👇 AQUÍ ESTÁ LA CLAVE
        self.fields["client"].label_from_instance = (
            lambda obj: obj.nombre
        )

        # Ordenar por nombre visible
        self.fields["client"].queryset = self.fields["client"].queryset.order_by("nombre")

        # Origen / destino (como ya lo tenías)
        self.fields["origen"].queryset = Location.objects.none()
        self.fields["destino"].queryset = Location.objects.none()

        client_id = None
        if self.is_bound:
            client_id = self.data.get("client")
        elif self.instance.pk:
            client_id = self.instance.client_id

        if client_id:
            qs = Location.objects.filter(client_id=client_id, deleted=False).order_by("nombre")
            self.fields["origen"].queryset = qs
            self.fields["destino"].queryset = qs
    
    def clean(self):
        cleaned = super().clean()

        client = cleaned.get("client")
        origen = cleaned.get("origen")
        destino = cleaned.get("destino")

        # No repetir misma ubicación
        if origen and destino and origen == destino:
            self.add_error("destino", "El destino no puede ser igual al origen.")

        # Coherencia cliente ↔ ubicaciones (por si postean manual)
        if client and origen and origen.client_id != client.id:
            self.add_error("origen", "El origen no pertenece al cliente seleccionado.")
        if client and destino and destino.client_id != client.id:
            self.add_error("destino", "El destino no pertenece al cliente seleccionado.")

        return cleaned

# =========================
# FORM PARA EDITAR SOLO TARIFAS
# =========================
class RouteTariffsForm(forms.ModelForm):
    class Meta:
        model = Route
        fields = [
            "tarifa_cliente",
            "pago_operador",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            field.widget.attrs.update({
                "class": "form-control form-control-sm"
            })