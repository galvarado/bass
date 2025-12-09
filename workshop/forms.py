# workshop/forms.py
from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet

from .models import WorkshopOrder
from trucks.models import Truck, ReeferBox
from warehouse.models import SparePartMovement


# =======================
#   FORMULARIO DE OT
# =======================
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

        # ===== Bootstrap pequeño =====
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

        # === Unidades vivas ===
        self.fields["truck"].queryset = Truck.all_objects.alive()
        self.fields["truck"].required = False

        self.fields["reefer_box"].queryset = ReeferBox.all_objects.alive()
        self.fields["reefer_box"].required = False

        # UX
        self.fields["descripcion"].widget.attrs.setdefault("rows", 3)
        self.fields["notas_internas"].widget.attrs.setdefault("rows", 3)

        # ===== CREACIÓN vs EDICIÓN =====
        if instance and instance.pk:
            # --- EDICIÓN ---
            self.fields["truck"].disabled = True
            self.fields["reefer_box"].disabled = True
            self.fields["descripcion"].disabled = True
            self.fields["estado"].required = True

        else:
            # --- CREACIÓN ---
            self.fields["estado"].initial = "ABIERTA"
            self.fields["estado"].required = False
            self.fields["descripcion"].required = True


# ================================
#   BUSCADOR
# ================================
class WorkshopOrderSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={
            "placeholder": "Económico, placas o descripción",
            "class": "form-control form-control-sm",
        }),
    )

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


# ================================
#   REFACCIONES USADAS EN OT
# ================================
class SparePartUsageForm(forms.ModelForm):
    """
    Formulario para capturar refacciones usadas en una orden de taller.
    La cantidad se captura en positivo, pero se convertirá a negativa al guardar.
    """

    class Meta:
        model = SparePartMovement
        fields = ["spare_part", "quantity", "unit_cost", "description"]
        labels = {
            "spare_part": "Refacción",
            "quantity": "Cantidad usada",
            "unit_cost": "Costo unitario",
            "description": "Descripción",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Bootstrap pequeño
        for f in self.fields.values():
            f.widget.attrs["class"] = "form-control form-control-sm"

        # Cantidad obligatoria si se captura refacción
        self.fields["quantity"].required = False

    def clean_quantity(self):
        qty = self.cleaned_data.get("quantity")
        if qty is None or qty == "":
            return None
        if qty <= 0:
            raise forms.ValidationError("La cantidad debe ser mayor que cero.")
        return qty


class BaseSparePartUsageFormSet(BaseInlineFormSet):
    def get_queryset(self):
        """
        Solo movimientos vivos y de tipo WORKSHOP_USAGE.
        """
        qs = super().get_queryset()
        return qs.filter(movement_type="WORKSHOP_USAGE", deleted=False)


SparePartUsageFormSet = inlineformset_factory(
    parent_model=WorkshopOrder,
    model=SparePartMovement,
    form=SparePartUsageForm,
    formset=BaseSparePartUsageFormSet,
    fk_name="workshop_order",
    extra=3,
    can_delete=True,
)
