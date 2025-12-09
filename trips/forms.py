# trips/forms.py
from django import forms
from django.db.models import Exists, OuterRef
from django.forms import inlineformset_factory
from django.apps import apps 

from .models import Trip, TransferType, TripStatus
from workshop.models import WorkshopOrder
from .models import (
    CartaPorteCFDI,
    CartaPorteLocation,
    CartaPorteGoods,
    CartaPorteTransportFigure,
)


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

from .models import (
    CartaPorteCFDI,
    CartaPorteLocation,
    CartaPorteGoods,
    CartaPorteTransportFigure,
)

class CartaPorteCFDIForm(forms.ModelForm):
    """
    Main form for CartaPorteCFDI.
    We define `customer` manually to avoid the "related model not loaded yet" error.
    """
    customer = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Cliente (Receptor)"
    )

    class Meta:
        model = CartaPorteCFDI
        # 👈 IMPORTANT: exclude `customer` so Django doesn't try to auto-generate it
        exclude = [
            "trip",
            "uuid",
            "pdf_url",
            "xml_url",
            "status",
            "last_error",
            "payload_snapshot",
            "response_snapshot",
            "created_at",
            "updated_at",
            "customer",  # 👈 avoid auto formfield creation
        ]
        widgets = {
            "type": forms.Select(attrs={"class": "form-control"}),
            "series": forms.TextInput(attrs={"class": "form-control"}),
            "folio": forms.TextInput(attrs={"class": "form-control"}),
            "uso_cfdi": forms.TextInput(attrs={"class": "form-control"}),
            "currency": forms.TextInput(attrs={"class": "form-control"}),
            "exchange_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001"}),
            "payment_form": forms.TextInput(attrs={"class": "form-control"}),
            "payment_method": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Lazily resolve the Customer model when the form is instantiated
        Client = apps.get_model("customers", "Client")  
        self.fields["customer"].queryset = Client.objects.all()

        # If instance has a customer, set the initial value
        if self.instance and self.instance.pk and getattr(self.instance, "customer_id", None):
            self.fields["customer"].initial = self.instance.customer


class CartaPorteLocationForm(forms.ModelForm):
    class Meta:
        model = CartaPorteLocation
        exclude = ["carta_porte"]
        widgets = {
            "tipo_ubicacion": forms.Select(attrs={"class": "form-control form-control-sm"}),
            "rfc": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "nombre": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "num_reg_id_trib": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "residencia_fiscal": forms.TextInput(attrs={"class": "form-control form-control-sm"}),

            "calle": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "numero_exterior": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "numero_interior": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "colonia": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "localidad": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "referencia": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "municipio": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "estado": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "pais": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "codigo_postal": forms.TextInput(attrs={"class": "form-control form-control-sm"}),

            "fecha_hora_salida_llegada": forms.DateTimeInput(
                attrs={"class": "form-control form-control-sm", "type": "datetime-local"}
            ),
            "distancia_recorrida_km": forms.NumberInput(attrs={"class": "form-control form-control-sm", "step": "0.01"}),

            "orden": forms.NumberInput(attrs={"class": "form-control form-control-sm"}),
        }

class CartaPorteGoodsForm(forms.ModelForm):
    class Meta:
        model = CartaPorteGoods
        exclude = ["carta_porte"]
        widgets = {
            "bienes_transp": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "descripcion": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "clave_unidad": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "unidad": forms.TextInput(attrs={"class": "form-control form-control-sm"}),

            "cantidad": forms.NumberInput(attrs={"class": "form-control form-control-sm", "step": "0.001"}),
            "peso_en_kg": forms.NumberInput(attrs={"class": "form-control form-control-sm", "step": "0.001"}),

            "material_peligroso": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "clave_material_peligroso": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "embalaje": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
        }

class CartaPorteTransportFigureForm(forms.ModelForm):
    class Meta:
        model = CartaPorteTransportFigure
        exclude = ["carta_porte"]
        widgets = {
            "tipo_figura": forms.Select(attrs={"class": "form-control form-control-sm"}),
            "rfc": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "nombre": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "num_licencia": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
        }

CartaPorteLocationFormSet = inlineformset_factory(
    parent_model=CartaPorteCFDI,
    model=CartaPorteLocation,
    form=CartaPorteLocationForm,
    extra=2,            # por ejemplo: 1 origen, 1 destino
    can_delete=True
)

CartaPorteGoodsFormSet = inlineformset_factory(
    parent_model=CartaPorteCFDI,
    model=CartaPorteGoods,
    form=CartaPorteGoodsForm,
    extra=3,            # número inicial de filas
    can_delete=True
)

CartaPorteTransportFigureFormSet = inlineformset_factory(
    parent_model=CartaPorteCFDI,
    model=CartaPorteTransportFigure,
    form=CartaPorteTransportFigureForm,
    extra=1,
    can_delete=True
)
