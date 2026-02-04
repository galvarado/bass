# trips/forms.py
from decimal import Decimal

from django import forms
from django.apps import apps
from django.db.models import Exists, OuterRef
from django.forms import inlineformset_factory
from django.forms.widgets import Select

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
    CartaPorteItem,
)

# =========================
# Trip forms (tu código)
# =========================

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

# =========================
# Carta Porte - Choices (7)
# =========================

CURRENCY_CHOICES = (
    ("MXN", "MXN"),
    ("USD", "USD"),
)

PAYMENT_METHOD_CHOICES = (
    ("PUE", "PUE - Pago en una sola exhibición"),
    ("PPD", "PPD - Pago en parcialidades o diferido"),
)

PAYMENT_FORM_CHOICES = (
    ("01", "01 - Efectivo"),
    ("02", "02 - Cheque nominativo"),
    ("03", "03 - Transferencia electrónica"),
    ("04", "04 - Tarjeta de crédito"),
    ("28", "28 - Tarjeta de débito"),
    ("99", "99 - Por definir"),
)

USO_CFDI_CHOICES = (
    ("S01", "S01 - Sin efectos fiscales"),
    ("G01", "G01 - Adquisición de mercancías"),
    ("G03", "G03 - Gastos en general"),
    ("I01", "I01 - Construcciones"),
    ("I04", "I04 - Equipo de cómputo y accesorios"),
)

CFDI_TYPE_CHOICES = (
    ("I", "Ingreso"),
    ("T", "Traslado"),
)

UNIDAD_CHOICES = (
    ("", "—"),
    ("H87", "Pieza (H87)"),
    ("KGM", "Kilogramo (KGM)"),
    ("LTR", "Litro (LTR)"),
    ("TNE", "Tonelada (TNE)"),
    ("MTR", "Metro (MTR)"),
    ("XBX", "Caja (XBX)"),
    ("XPK", "Paquete (XPK)"),
    ("XBG", "Bolsa (XBG)"),
)

# =========================
# Goods Select with data-*
# =========================

class MercanciaSelectWithData(Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)

        inst = getattr(value, "instance", None)
        if inst is not None:
            option["attrs"]["data-clave"] = getattr(inst, "clave", "") or ""
            option["attrs"]["data-fraccion"] = getattr(inst, "fraccion_arancelaria", "") or ""
            ce_uuid = getattr(inst, "comercio_exterior_uuid", None)
            option["attrs"]["data-uuidce"] = str(ce_uuid) if ce_uuid else ""

        return option

# =========================
# Carta Porte CFDI form
# =========================

class CartaPorteCFDIForm(forms.ModelForm):
    customer = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={"class": "form-control form-control-sm"}),
        label="Cliente (Receptor)",
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
            # CFDI base (7 ✅ con selects)
            "type": forms.Select(choices=CFDI_TYPE_CHOICES, attrs={"class": "form-control form-control-sm"}),
            "series": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "folio": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "uso_cfdi": forms.Select(choices=USO_CFDI_CHOICES, attrs={"class": "form-control form-control-sm"}),
            "currency": forms.Select(choices=CURRENCY_CHOICES, attrs={"class": "form-control form-control-sm"}),
            "exchange_rate": forms.NumberInput(attrs={"class": "form-control form-control-sm", "step": "0.0001"}),
            "payment_form": forms.Select(choices=PAYMENT_FORM_CHOICES, attrs={"class": "form-control form-control-sm"}),
            "payment_method": forms.Select(choices=PAYMENT_METHOD_CHOICES, attrs={"class": "form-control form-control-sm"}),

            # Encabezado CP
            "fecha_salida": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control form-control-sm"},
                format="%Y-%m-%dT%H:%M",
            ),
            "fecha_llegada": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control form-control-sm"},
                format="%Y-%m-%dT%H:%M",
            ),
            "itrn_us_entry": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "pedimento": forms.TextInput(attrs={"class": "form-control form-control-sm"}),

            "subtotal": forms.NumberInput(attrs={"class": "form-control form-control-sm", "step": "0.01"}),
            "iva": forms.NumberInput(attrs={"class": "form-control form-control-sm", "step": "0.01"}),
            "retencion": forms.NumberInput(attrs={"class": "form-control form-control-sm", "step": "0.01"}),
            "total": forms.NumberInput(attrs={"class": "form-control form-control-sm", "step": "0.01"}),
            "observations": forms.Textarea(attrs={"class": "form-control form-control-sm", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        Client = apps.get_model("customers", "Client")
        qs = Client.objects.all().order_by("nombre")
        self.fields["customer"].queryset = qs
        self.fields["customer"].label_from_instance = lambda o: o.nombre

        # Para que al editar se vea bien en el input datetime-local
        for f in ("fecha_salida", "fecha_llegada"):
            if self.instance and getattr(self.instance, f, None):
                self.initial[f] = getattr(self.instance, f).strftime("%Y-%m-%dT%H:%M")

        if self.instance and self.instance.pk and getattr(self.instance, "customer_id", None):
            self.fields["customer"].initial = self.instance.customer

        # subtotal y total readonly (en UI se postean hidden, pero estos campos quedan disabled)
        if "subtotal" in self.fields:
            self.fields["subtotal"].disabled = True
        if "total" in self.fields:
            self.fields["total"].disabled = True

    def clean(self):
        cleaned = super().clean()
        for k in ["iva", "retencion"]:
            if k in cleaned and cleaned[k] is None:
                cleaned[k] = Decimal("0.00")
        return cleaned
class CartaPorteLocationForm(forms.ModelForm):
    # ⬅️ OVERRIDE de campos (rompe el max_length del modelo SOLO en el form)
    estado = forms.CharField(required=False, max_length=50)
    pais = forms.CharField(required=False, max_length=50)
    rfc = forms.CharField(required=False, max_length=13)

    class Meta:
        model = CartaPorteLocation
        fields = "__all__"

    ESTADO_SAT_MAP = {
        "Aguascalientes": "AGS",
        "Baja California": "BCN",
        "Baja California Sur": "BCS",
        "Campeche": "CAM",
        "Chiapas": "CHP",
        "Chihuahua": "CHH",
        "Ciudad de México": "CMX",
        "Coahuila": "COA",
        "Colima": "COL",
        "Durango": "DUR",
        "Guanajuato": "GUA",
        "Guerrero": "GRO",
        "Hidalgo": "HID",
        "Jalisco": "JAL",
        "México": "MEX",
        "Michoacán": "MIC",
        "Morelos": "MOR",
        "Nayarit": "NAY",
        "Nuevo León": "NLE",
        "Oaxaca": "OAX",
        "Puebla": "PUE",
        "Querétaro": "QUE",
        "Quintana Roo": "ROO",
        "San Luis Potosí": "SLP",
        "Sinaloa": "SIN",
        "Sonora": "SON",
        "Tabasco": "TAB",
        "Tamaulipas": "TAM",
        "Tlaxcala": "TLA",
        "Veracruz": "VER",
        "Yucatán": "YUC",
        "Zacatecas": "ZAC",
    }

    def clean_estado(self):
        estado = self.cleaned_data.get("estado", "")
        return self.ESTADO_SAT_MAP.get(estado, "")[:3]

    def clean_pais(self):
        return "MX"

# =========================
# Carta Porte Goods form
# =========================

class CartaPorteGoodsForm(forms.ModelForm):
    mercancia = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label="Mercancía",
        widget=MercanciaSelectWithData(attrs={"class": "form-control form-control-sm js-mercancia"}),
    )

    class Meta:
        model = CartaPorteGoods
        exclude = ["carta_porte", "mercancia"]
        widgets = {
            "cantidad": forms.NumberInput(attrs={"class": "form-control form-control-sm", "step": "0.001"}),
            "unidad": forms.Select(choices=UNIDAD_CHOICES, attrs={"class": "form-control form-control-sm"}),
            "embalaje": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "peso_en_kg": forms.NumberInput(attrs={"class": "form-control form-control-sm", "step": "0.001"}),
            "valor_mercancia": forms.NumberInput(attrs={"class": "form-control form-control-sm", "step": "0.01"}),
            "moneda": forms.Select(choices=CURRENCY_CHOICES, attrs={"class": "form-control form-control-sm js-moneda"}),
            "pedimento": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
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
            # ✅ autollenado defensivo (solo si existen los campos)
            if hasattr(instance, "clave") and not (getattr(instance, "clave", "") or "").strip():
                instance.clave = getattr(merc, "clave", "") or ""

            if hasattr(instance, "fraccion_arancelaria") and not (getattr(instance, "fraccion_arancelaria", "") or "").strip():
                instance.fraccion_arancelaria = getattr(merc, "fraccion_arancelaria", "") or ""

            if hasattr(instance, "uuid_comercio_exterior") and not (getattr(instance, "uuid_comercio_exterior", "") or "").strip():
                ce_uuid = getattr(merc, "comercio_exterior_uuid", None)
                instance.uuid_comercio_exterior = str(ce_uuid) if ce_uuid else ""

            # moneda por default desde carta si existe
            if not (instance.moneda or "").strip() and getattr(instance.carta_porte, "currency", None):
                instance.moneda = instance.carta_porte.currency

        if commit:
            instance.save()
        return instance

# =========================
# Carta Porte Item form
# =========================

class CartaPorteItemForm(forms.ModelForm):
    class Meta:
        model = CartaPorteItem
        exclude = ["carta_porte", "subtotal", "iva_monto", "ret_iva_monto", "importe", "orden"]
        widgets = {
            "cantidad": forms.NumberInput(attrs={"class": "form-control form-control-sm js-itm-cant", "step": "0.001"}),
            "unidad": forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "Ej. H87"}),
            "producto": forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "SKU / Producto"}),
            "descripcion": forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "Descripción"}),
            "precio": forms.NumberInput(attrs={"class": "form-control form-control-sm js-itm-precio text-right", "step": "0.01"}),
            "descuento": forms.NumberInput(attrs={"class": "form-control form-control-sm js-itm-desc text-right", "step": "0.01"}),
            "iva_pct": forms.NumberInput(attrs={"class": "form-control form-control-sm js-itm-iva text-right", "step": "0.01"}),
            "ret_iva_pct": forms.NumberInput(attrs={"class": "form-control form-control-sm js-itm-retiva text-right", "step": "0.01"}),
        }

    def clean(self):
        cleaned = super().clean()
        for k in ["cantidad", "precio", "descuento", "iva_pct", "ret_iva_pct"]:
            if cleaned.get(k) is None:
                cleaned[k] = Decimal("0.00")
        return cleaned

# =========================
# Formsets (lazy)
# =========================

def get_carta_porte_location_formset():
    return inlineformset_factory(
        CartaPorteCFDI,
        CartaPorteLocation,
        form=CartaPorteLocationForm,
        extra=0,
        can_delete=False,
    )

def get_carta_porte_goods_formset():
    return inlineformset_factory(
        CartaPorteCFDI,
        CartaPorteGoods,
        form=CartaPorteGoodsForm,
        extra=1,
        can_delete=True,
    )

def get_carta_porte_item_formset():
    return inlineformset_factory(
        CartaPorteCFDI,
        CartaPorteItem,
        form=CartaPorteItemForm,
        extra=1,
        can_delete=True,
    )
