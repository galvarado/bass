# trips/forms.py
from django import forms
from django.apps import apps
from django.db.models import Exists, OuterRef
from django.forms import inlineformset_factory

from operators.models import Operator, CrossBorderCapability
from workshop.models import WorkshopOrder

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

        qs = Operator.objects.filter(
            deleted=False,
            status="ALTA",
            cross_border__in=[
                CrossBorderCapability.PUEDE,
                CrossBorderCapability.SOLO_CRUCE,
            ],
        ).order_by("nombre")
        self.fields["transfer_operator"].queryset = qs

        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                base = field.widget.attrs.get("class", "")
                field.widget.attrs.update({"class": (base + " form-control form-control-sm").strip()})

        for k in ["client", "route", "operator", "truck", "reefer_box", "transfer_operator", "clasificacion", "temp_scale"]:
            if k in self.fields and isinstance(self.fields[k].widget, forms.Select):
                self.fields[k].widget.attrs.update({"class": "form-control form-control-sm"})

        if "temperatura_min" in self.fields:
            self.fields["temperatura_min"].widget = forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            )
        if "temperatura_max" in self.fields:
            self.fields["temperatura_max"].widget = forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            )

        if "client" in self.fields:
            self.fields["client"].label_from_instance = lambda obj: obj.nombre
            self.fields["client"].empty_label = "Selecciona cliente…"

        if "operator" in self.fields:
            self.fields["operator"].queryset = self.fields["operator"].queryset.order_by("nombre")

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

        if route and client and route.client_id != client.id:
            self.add_error("route", "La ruta no pertenece a este cliente.")

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
    customer = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Cliente (Receptor)"
    )

    class Meta:
        model = CartaPorteCFDI
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
            "customer",
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
        Client = apps.get_model("customers", "Client")
        qs = Client.objects.all().order_by("nombre")
        self.fields["customer"].queryset = qs
        self.fields["customer"].label_from_instance = lambda o: o.nombre

        if self.instance and self.instance.pk and getattr(self.instance, "customer_id", None):
            self.fields["customer"].initial = self.instance.customer


class CartaPorteLocationForm(forms.ModelForm):
    class Meta:
        model = CartaPorteLocation
        exclude = [
            "carta_porte",
            "distancia_recorrida_km",
            "fecha_hora_salida_llegada",
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
    mercancia = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label="Mercancía (Catálogo)",
        widget=forms.Select(attrs={"class": "form-control form-control-sm js-mercancia"})
    )

    class Meta:
        model = CartaPorteGoods
        exclude = ["carta_porte", "mercancia"]
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        Mercancia = apps.get_model("goods", "Mercancia")
        self.fields["mercancia"].queryset = Mercancia.objects.filter(deleted=False).order_by("nombre")
        self.fields["mercancia"].empty_label = "Selecciona mercancía…"
        self.fields["mercancia"].label_from_instance = lambda m: f"{m.nombre}"

        if self.instance and getattr(self.instance, "mercancia_id", None):
            self.fields["mercancia"].initial = self.instance.mercancia_id

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.mercancia = self.cleaned_data.get("mercancia")

        merc = instance.mercancia
        if merc:
            if not (instance.bienes_transp or "").strip():
                instance.bienes_transp = merc.clave
            if not (instance.descripcion or "").strip():
                instance.descripcion = merc.nombre

        if commit:
            instance.save()
        return instance


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


# -----------------------
# ✅ Formsets LAZY (no se ejecutan en import time)
# -----------------------

def get_carta_porte_location_formset():
    return inlineformset_factory(
        CartaPorteCFDI,
        CartaPorteLocation,
        form=CartaPorteLocationForm,
        extra=0,
        can_delete=False,
        max_num=2,
        validate_max=True,
    )

def get_carta_porte_goods_formset():
    return inlineformset_factory(
        CartaPorteCFDI,
        CartaPorteGoods,
        form=CartaPorteGoodsForm,
        extra=1,
        can_delete=True,
    )

def get_carta_porte_transport_figure_formset():
    return inlineformset_factory(
        CartaPorteCFDI,
        CartaPorteTransportFigure,
        form=CartaPorteTransportFigureForm,
        extra=1,
        can_delete=True,
    )
