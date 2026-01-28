# trips/forms.py
from django import forms
from django.db.models import Exists, OuterRef
from django.forms import inlineformset_factory
from django.apps import apps 
from operators.models import Operator, CrossBorderCapability
from .models import Trip, TransferType, TripStatus
from workshop.models import WorkshopOrder
from .models import (
    CartaPorteCFDI,
    CartaPorteLocation,
    CartaPorteGoods,
    CartaPorteTransportFigure,
)

# trips/forms.py
from django import forms
from django.db.models import Exists, OuterRef
from django.urls import reverse
from workshop.models import WorkshopOrder

from .models import Trip, TransferType, TripStatus

from .models import (
    Trip,
    TransferType,
    TripStatus,
    TripClassification,
    TemperatureScale,
    CartaPorteCFDI,
    CartaPorteLocation,
    CartaPorteGoods,
    CartaPorteTransportFigure,
)


class TripForm(forms.ModelForm):
    class Meta:
        model = Trip
        fields = [
            "client",
            "route",
            "operator",
            "truck",
            "reefer_box",
            "transfer_operator",

            # ✅ NUEVOS
            "producto",
            "clasificacion",
            "temp_scale",
            "temperatura_min",
            "temperatura_max",

            "observations",
        ]
        widgets = {
            "observations": forms.Textarea(attrs={"rows": 3}),
            "producto": forms.TextInput(attrs={"placeholder": "Ej. Hortaliza, Carne, Congelados..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Transfer operators (cruce)
        qs = Operator.objects.filter(
            deleted=False,
            status="ALTA",
            cross_border__in=[
                CrossBorderCapability.PUEDE,
                CrossBorderCapability.SOLO_CRUCE,
            ],
        ).order_by("nombre")
        self.fields["transfer_operator"].queryset = qs

        # Estilo Bootstrap (sm)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                base = field.widget.attrs.get("class", "")
                field.widget.attrs.update({"class": (base + " form-control form-control-sm").strip()})

        # selects sm
        for k in ["client", "route", "operator", "truck", "reefer_box", "transfer_operator", "clasificacion", "temp_scale"]:
            if k in self.fields and isinstance(self.fields[k].widget, (forms.Select,)):
                self.fields[k].widget.attrs.update({"class": "form-control form-control-sm"})

        # Temperatura: inputs numéricos con step
        if "temperatura_min" in self.fields:
            self.fields["temperatura_min"].widget = forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            )
        if "temperatura_max" in self.fields:
            self.fields["temperatura_max"].widget = forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            )

        # labels / empty labels
        if "client" in self.fields:
            self.fields["client"].label_from_instance = lambda obj: obj.nombre
            self.fields["client"].empty_label = "Selecciona cliente…"

        if "operator" in self.fields:
            self.fields["operator"].queryset = self.fields["operator"].queryset.order_by("nombre")

        # --- Route: vacío hasta elegir cliente ---
        if "route" in self.fields:
            qs_route = self.fields["route"].queryset.select_related("origen", "destino", "client")

            client_id = None
            if self.is_bound:
                client_id = self.data.get("client") or self.data.get("client_id")

            if not client_id and getattr(self.instance, "client_id", None):
                client_id = self.instance.client_id

            if not client_id:
                client_initial = self.initial.get("client")
                client_id = getattr(client_initial, "id", None) or client_initial

            if client_id:
                qs_route = qs_route.filter(client_id=client_id).order_by("origen__nombre", "destino__nombre")
                self.fields["route"].queryset = qs_route
            else:
                self.fields["route"].queryset = qs_route.none()

            self.fields["route"].empty_label = "Selecciona ruta…"

        # === Filtro de unidades SOLO al crear viaje ===
        if not self.instance.pk:
            allowed_estados = ["TERMINADA", "CANCELADA"]

            if "truck" in self.fields:
                qs_trucks = self.fields["truck"].queryset
                blocking_ot_truck = WorkshopOrder.objects.filter(
                    deleted=False,
                    truck=OuterRef("pk"),
                ).exclude(estado__in=allowed_estados)

                self.fields["truck"].queryset = (
                    qs_trucks
                    .annotate(has_blocking_ot=Exists(blocking_ot_truck))
                    .filter(has_blocking_ot=False)
                    .order_by("numero_economico")
                )

            if "reefer_box" in self.fields:
                qs_boxes = self.fields["reefer_box"].queryset
                blocking_ot_box = WorkshopOrder.objects.filter(
                    deleted=False,
                    reefer_box=OuterRef("pk"),
                ).exclude(estado__in=allowed_estados)

                self.fields["reefer_box"].queryset = (
                    qs_boxes
                    .annotate(has_blocking_ot=Exists(blocking_ot_box))
                    .filter(has_blocking_ot=False)
                    .order_by("numero_economico")
                )

    def clean_observations(self):
        return (self.cleaned_data.get("observations") or "").strip()

    def clean_producto(self):
        return (self.cleaned_data.get("producto") or "").strip()

    def clean(self):
        cleaned = super().clean()

        client = cleaned.get("client")
        route = cleaned.get("route")

        # coherencia client-route
        if route and client and route.client_id != client.id:
            self.add_error("route", "La ruta no pertenece a este cliente.")

        # ✅ Validación de temperatura
        tmin = cleaned.get("temperatura_min")
        tmax = cleaned.get("temperatura_max")
        if tmin is not None and tmax is not None and tmin > tmax:
            self.add_error("temperatura_min", "La temperatura mínima no puede ser mayor que la máxima.")
            self.add_error("temperatura_max", "La temperatura máxima no puede ser menor que la mínima.")

        return cleaned


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

    transfer_operator = forms.ChoiceField(
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
        qs = Client.objects.all().order_by("nombre")
        self.fields["customer"].queryset = qs
        self.fields["customer"].label_from_instance = lambda o: o.nombre

        # If instance has a customer, set the initial value
        if self.instance and self.instance.pk and getattr(self.instance, "customer_id", None):
            self.fields["customer"].initial = self.instance.customer


class CartaPorteLocationForm(forms.ModelForm):
    class Meta:
        model = CartaPorteLocation
        exclude = [
            "carta_porte",
            "distancia_recorrida_km",         # ❌ fuera
            "fecha_hora_salida_llegada",      # ❌ fuera (la tomamos del Trip)
        ]
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
    extra=0,            # ✅ no filas extra
    can_delete=False,   # ✅ no se elimina
    max_num=2,          # ✅ solo 2
    validate_max=True,
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
