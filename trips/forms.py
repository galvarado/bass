# trips/forms.py
from django import forms
from django.db.models import Exists, OuterRef

from .models import Trip, TransferType, TripStatus
from workshop.models import WorkshopOrder



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

        # Estilo compacto y consistente
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                field.widget.attrs.update({
                    "class": "form-control form-control-sm"
                })

        # Ordenar selects por nombre
        if "origin" in self.fields:
            self.fields["origin"].queryset = self.fields["origin"].queryset.order_by("nombre")
        if "destination" in self.fields:
            self.fields["destination"].queryset = self.fields["destination"].queryset.order_by("nombre")
        if "operator" in self.fields:
            self.fields["operator"].queryset = self.fields["operator"].queryset.order_by("nombre")

        # === Filtro de unidades SOLO al crear viaje ===
        # (para no romper validación al editar)
        if not self.instance.pk:
            allowed_estados = ["TERMINADA", "CANCELADA"]

            # ---- CAMIONES ----
            if "truck" in self.fields:
                qs_trucks = self.fields["truck"].queryset

                # OT que bloquean el camión: cualquier OT viva con estado != TERMINADA/CANCELADA
                blocking_ot_truck = WorkshopOrder.objects.filter(
                    deleted=False,
                    truck=OuterRef("pk"),
                ).exclude(
                    estado__in=allowed_estados
                )

                qs_trucks = (
                    qs_trucks
                    .annotate(has_blocking_ot=Exists(blocking_ot_truck))
                    .filter(has_blocking_ot=False)
                    .order_by("numero_economico")
                )

                self.fields["truck"].queryset = qs_trucks

            # ---- CAJAS REEFER ----
            if "reefer_box" in self.fields:
                qs_boxes = self.fields["reefer_box"].queryset

                blocking_ot_box = WorkshopOrder.objects.filter(
                    deleted=False,
                    reefer_box=OuterRef("pk"),
                ).exclude(
                    estado__in=allowed_estados
                )

                qs_boxes = (
                    qs_boxes
                    .annotate(has_blocking_ot=Exists(blocking_ot_box))
                    .filter(has_blocking_ot=False)
                    .order_by("numero_economico")  # o 'numero' si así se llama en ReeferBox
                )

                self.fields["reefer_box"].queryset = qs_boxes

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
