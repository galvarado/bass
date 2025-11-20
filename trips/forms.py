# trips/forms.py
from django import forms
from .models import Trip, TransferType, TripStatus


class TripForm(forms.ModelForm):
    class Meta:
        model = Trip
        fields = [
            # Datos base del viaje
            "origin",
            "destination",
            "operator",
            "truck",
            "reefer_box",
            "transfer",
            "observations",
            # Los tiempos de monitoreo los dejamos fuera del alta normal;
            # se editarán en la vista de monitoreo.
            # "arrival_origin_at",
            # "departure_origin_at",
            # "arrival_destination_at",
        ]
        widgets = {
            "observations": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Estilo compacto y consistente (igual que en clientes/operadores)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                field.widget.attrs.update({
                    "class": "form-control form-control-sm"
                })

        # Si quieres, puedes aquí ordenar selects por nombre:
        if "origin" in self.fields:
            self.fields["origin"].queryset = self.fields["origin"].queryset.order_by("nombre")
        if "destination" in self.fields:
            self.fields["destination"].queryset = self.fields["destination"].queryset.order_by("nombre")
        if "operator" in self.fields:
            self.fields["operator"].queryset = self.fields["operator"].queryset.order_by("nombre")
        if "truck" in self.fields:
            self.fields["truck"].queryset = self.fields["truck"].queryset.order_by("numero_economico")
        if "reefer_box" in self.fields:
            self.fields["reefer_box"].queryset = self.fields["reefer_box"].queryset.order_by("numero_economico")

    # Normalizaciones básicas (opcional)
    def clean_observations(self):
        v = self.cleaned_data.get("observations") or ""
        return v.strip()


class TripSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={
            "placeholder": "Origen, destino, operador, unidad, caja u observaciones",
            "class": "form-control form-control-sm",
        }),
    )

    status = forms.ChoiceField(
        required=False,
        label="Estatus",
        choices=(
            ("", "Todos"),
            (TripStatus.PROGRAMADO, "Programado"),
            (TripStatus.EN_CURSO, "En curso"),
            (TripStatus.COMPLETADO, "Completado"),
            (TripStatus.CANCELADO, "Cancelado"),
        ),
        widget=forms.Select(attrs={"class": "form-control form-control-sm"}),
    )

    transfer = forms.ChoiceField(
        required=False,
        label="Transfer",
        choices=(
            ("", "Todos"),
            (TransferType.NINGUNO, "Sin transfer"),
            (TransferType.FULL, "Full"),
            (TransferType.VACIO, "Vacío"),
            (TransferType.CRUCE, "Cruce"),
            (TransferType.INTERCAMBIO, "Intercambio"),
        ),
        widget=forms.Select(attrs={"class": "form-control form-control-sm"}),
    )
