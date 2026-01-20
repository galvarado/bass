# operators/forms.py
from django import forms
from django.utils import timezone
from .models import Operator, CrossBorderCapability


from django_postalcodes_mexico.models import PostalCode as PC  # ajusta alias si hace falta

class OperatorForm(forms.ModelForm):
    class Meta:
        model = Operator
        fields = [
            "nombre","rfc","curp","tipo_sangre","imss",
            "fecha_nacimiento","fecha_ingreso","puesto",
            "calle","no_ext","colonia","colonia_sat",
            "municipio","estado","pais","cp","telefono",
            "tipo_contrato","tipo_regimen","tipo_jornada",
            "tipo_liquidacion","periodicidad","cuenta_bancaria","cuenta",
            "poblacion",
            "sueldo_fijo","comision","tope",
            "ine","ine_vencimiento","licencia_federal","licencia_federal_vencimiento",
            "visa","visa_vencimiento","pasaporte","pasaporte_vencimiento",
            "examen_medico","examen_medico_vencimiento","rcontrol","rcontrol_vencimiento",
            "antidoping","antidoping_vencimiento",
            "cross_border",         
            "status",
        ]
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_ingreso": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "ine_vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "licencia_federal_vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "visa_vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "pasaporte_vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "examen_medico_vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "rcontrol_vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "antidoping_vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            # Dirección
            "cp": forms.TextInput(attrs={"maxlength": 5, "pattern": r"\d{5}"}),
            "estado": forms.TextInput(attrs={"readonly": "readonly"}),
            "municipio": forms.TextInput(attrs={"readonly": "readonly"}),
            "poblacion": forms.TextInput(attrs={"readonly": "readonly"}),  # editable, lo llenamos con d_ciudad si existe
            "colonia": forms.Select(),
            "colonia_sat": forms.TextInput(attrs={"readonly": "readonly"}),  # ← ahora solo lectura
            "cross_border": forms.Select(),
            "pais": forms.TextInput(attrs={"readonly": "readonly"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            cls = "form-control form-control-sm"
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                field.widget.attrs.update({"class": cls})
        for f in self.fields:
            if isinstance(self.fields[f].widget, forms.DateInput):
                self.fields[f].input_formats = ["%Y-%m-%d"]

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

    # --- Validaciones de fechas (igual que ya tenías) ---
    def _check_future_or_present(self, fname):
        v = self.cleaned_data.get(fname)
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

    # --- Normalización de texto ---
    def clean_nombre(self): return self.cleaned_data["nombre"].strip().title()
    def clean_puesto(self):
        v = self.cleaned_data.get("puesto")
        return v.strip().title() if v else v

    # --- Coherencia CP/Colonia y autocompletar municipio/poblacion en servidor ---
    def clean(self):
        cleaned = super().clean()
        cp = (cleaned.get("cp") or "").strip()
        colonia = (cleaned.get("colonia") or "").strip()
        if cp and colonia:
            if not PC.objects.filter(d_codigo=cp, d_asenta=colonia).exists():
                self.add_error("colonia", "La colonia no corresponde al código postal ingresado.")

        # Autorellenar municipio/poblacion si vienen vacíos pero hay CP
        if cp.isdigit() and len(cp) == 5:
            if not cleaned.get("municipio"):
                mun = (PC.objects.filter(d_codigo=cp)
                        .exclude(d_mnpio__isnull=True).exclude(D_mnpio="")
                        .values_list("D_mnpio", flat=True).order_by("D_mnpio").first())
                if not mun:
                    mun = (PC.objects.filter(d_codigo=cp)
                            .exclude(d_ciudad__isnull=True).exclude(d_ciudad="")
                            .values_list("d_ciudad", flat=True).order_by("d_ciudad").first())
                if mun:
                    cleaned["municipio"] = mun
                    self.data = self.data.copy(); self.data["municipio"] = mun  # refleja en POST

            if not cleaned.get("poblacion"):
                ciu = (PC.objects.filter(d_codigo=cp)
                        .exclude(d_ciudad__isnull=True).exclude(d_ciudad="")
                        .values_list("d_ciudad", flat=True).order_by("d_ciudad").first())
                if ciu:
                    cleaned["poblacion"] = ciu
                    self.data = self.data.copy(); self.data["poblacion"] = ciu

        return cleaned

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
