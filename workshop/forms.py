# workshop/forms.py
from django import forms

from .models import WorkshopOrder
from trucks.models import Truck, ReeferBox


class WorkshopOrderForm(forms.ModelForm):
    class Meta:
        model = WorkshopOrder
        fields = [
            "truck",
            "reefer_box",
            "fecha_salida_estimada",
            "descripcion",
            "estado",
            "costo_mano_obra",
            "costo_refacciones",
            "otros_costos",
            "notas_internas",
        ]
        widgets = {
            "fecha_salida_estimada": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        instance = getattr(self, "instance", None)

        # ===== Estilo Bootstrap pequeño =====
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                cls = "form-control form-control-sm"
                existing = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = (existing + " " + cls).strip()

        # Formato fecha
        if isinstance(self.fields["fecha_salida_estimada"].widget, forms.DateInput):
            self.fields["fecha_salida_estimada"].input_formats = ["%Y-%m-%d"]

        # Solo unidades vivas
        self.fields["truck"].queryset = Truck.all_objects.alive()
        self.fields["truck"].required = False

        self.fields["reefer_box"].queryset = ReeferBox.all_objects.alive()
        self.fields["reefer_box"].required = False

        # UX
        self.fields["descripcion"].widget.attrs.setdefault("rows", 3)
        self.fields["notas_internas"].widget.attrs.setdefault("rows", 3)

        # ===== Lógica según creación / edición =====
        if instance and instance.pk:
            # --- EDICIÓN ---
            # No permitir cambiar la unidad ni la descripción
            self.fields["truck"].disabled = True
            self.fields["reefer_box"].disabled = True
            self.fields["descripcion"].disabled = True

            # Estado editable en edición
            self.fields["estado"].required = True

        else:
            # --- CREACIÓN ---
            # Estado no se usa en el template al crear, pero forzamos default
            self.fields["estado"].initial = "ABIERTA"
            self.fields["estado"].required = False

            # En creación la descripción sí debe ser obligatoria
            self.fields["descripcion"].required = True


class WorkshopOrderSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={
            "placeholder": "Económico, placas o descripción",
            "class": "form-control form-control-sm",
        }),
    )

    # Filtro virtual de tipo de unidad (no es campo del modelo)
    tipo_unidad = forms.ChoiceField(
        required=False,
        label="Tipo de unidad",
        choices=[
            ("", "Camión y caja"),
            ("TRUCK", "Solo camiones"),
            ("BOX", "Solo cajas"),
        ],
        widget=forms.Select(attrs={"class": "form-control form-control-sm"}),
    )
