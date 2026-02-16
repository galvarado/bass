# trips/models.py
from django.db import models
from customers.models import Client
from trucks.models import Truck, ReeferBox
from operators.models import Operator
from locations.models import Location, Route
from django.utils import timezone
from decimal import Decimal

class TransferType(models.TextChoices):
    NINGUNO = "NINGUNO", "Ninguno"
    FULL = "FULL", "Full"
    VACIO = "VACÍO", "Vacío"
    CRUCE = "CRUCE", "Cruce"
    INTERCAMBIO = "INTERCAMBIO", "Intercambio"


class TripStatus(models.TextChoices):
    PROGRAMADO = "PROGRAMADO", "Programado"
    EN_ORIGEN = "EN_ORIGEN", "En origen"
    EN_CURSO = "EN_CURSO", "En curso"
    EN_DESTINO = "EN_DESTINO", "En destino"
    COMPLETADO = "COMPLETADO", "Completado"
    CANCELADO = "CANCELADO", "Cancelado"

class TripClassification(models.TextChoices):
    NACIONAL = "NACIONAL", "Nacional"
    EXPORTACION = "EXPORTACION", "Exportación"


class TemperatureScale(models.TextChoices):
    F = "F", "Fahrenheit (°F)"
    C = "C", "Celsius (°C)"


class Trip(models.Model):
    """
    Un viaje con origen/destino, operador, camión y caja obligatoria.
    Permite registrar tiempos reales durante el monitoreo.
    """
    operator = models.ForeignKey(
        Operator,
        on_delete=models.PROTECT,
        related_name="trips",
        verbose_name="Operador",
    )
    truck = models.ForeignKey(
        Truck,
        on_delete=models.PROTECT,
        related_name="trips",
        verbose_name="Camión",
    )
    reefer_box = models.ForeignKey(
        ReeferBox,
        on_delete=models.PROTECT,
        related_name="trips",
    )
    transfer_operator = models.ForeignKey(
        Operator,
        on_delete=models.PROTECT,
        related_name="trips_as_transfer",
        null=True,
        blank=True,
        verbose_name="Operador de cruce (transfer)",
    )

    status = models.CharField(
        max_length=20,
        choices=TripStatus.choices,
        default=TripStatus.PROGRAMADO,
        verbose_name="Estatus",
    )

    # Tiempos de monitoreo
    arrival_origin_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Hora de llegada al origen",
    )
    departure_origin_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Hora de salida del origen",
    )
    arrival_destination_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Hora de llegada al destino",
    )
    client = models.ForeignKey(
    Client,
        on_delete=models.PROTECT,
        related_name="trips",
        null=True,
        blank=True,
    )
    route = models.ForeignKey(
        "locations.Route",
        on_delete=models.PROTECT,
        related_name="trips",
        null=True,
        blank=True,
    )

    # Snapshots (copied from route at creation time)
    tarifa_cliente_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    pago_operador_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    pago_transfer_propio_snapshot = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    pago_transfer_solo_cruce_snapshot = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    producto = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Producto",
        help_text="Hortaliza, Congelados, etc.)",
    )
    clasificacion = models.CharField(
        max_length=20,
        choices=TripClassification.choices,
        default=TripClassification.NACIONAL,
        verbose_name="Clasificación",
    )
    temp_scale = models.CharField(
        max_length=1,
        choices=TemperatureScale.choices,
        default=TemperatureScale.C,
        verbose_name="Escala de temperatura",
    )
    temperatura_min = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Temperatura mínima",
        help_text="",
    )
    temperatura_max = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Temperatura máxima",
        help_text="",
    )

     # --- Soft delete ---
    deleted = models.BooleanField(default=False, db_index=True)

    # Managers (mismo patrón que Operator)
    objects = models.Manager()


    class Meta:
        verbose_name = "Viaje"
        verbose_name_plural = "Viajes"
        ordering = ["-id"]

    def apply_route_pricing_snapshot(self, force=False):
        """
        Copies current Route pricing into the trip.
        - force=False: only fills if snapshots are still zero/unset (good on create)
        - force=True: overwrites (use carefully)
        """
        r = self.route
        if not r:
            return

        if force or self.tarifa_cliente_snapshot == Decimal("0.00"):
            self.tarifa_cliente_snapshot = r.tarifa_cliente or Decimal("0.00")
        if force or self.pago_operador_snapshot == Decimal("0.00"):
            self.pago_operador_snapshot = r.pago_operador or Decimal("0.00")
        if force or self.pago_transfer_propio_snapshot == Decimal("0.00"):
            self.pago_transfer_propio_snapshot = r.pago_transfer_propio or Decimal("0.00")

        if force or self.pago_transfer_solo_cruce_snapshot == Decimal("0.00"):
            self.pago_transfer_solo_cruce_snapshot = r.pago_transfer_solo_cruce or Decimal("0.00")


    @property
    def total_cobro_cliente(self):
        return (self.tarifa_cliente_snapshot or 0)

    @property
    def total_pago_operador(self):
        return (self.pago_operador_snapshot or 0)

    def __str__(self):
        r = self.route
        route_str = f"{r.origen} → {r.destino}" if r else "Sin ruta"
        return f"{route_str} | {self.operator} | {self.truck} + {self.reefer_box}"


class CartaPorteCFDI(models.Model):
    TYPE_CHOICES = [
        ("I", "Ingreso"),
        ("T", "Traslado"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("ready", "Ready to stamp"),
        ("stamped", "Stamped"),
        ("canceled", "Canceled"),
        ("error", "Error"),
    ]

    trip = models.OneToOneField(
        "trips.Trip",
        on_delete=models.CASCADE,
        related_name="carta_porte_cfdi",
    )

    # --- Datos CFDI generales ---
    type = models.CharField(max_length=1, choices=TYPE_CHOICES, default="T")
    series = models.CharField(max_length=25, blank=True, null=True)
    folio = models.CharField(max_length=40, blank=True, null=True)

    uso_cfdi = models.CharField(max_length=3, default="S01")  # Sin efectos fiscales
    currency = models.CharField(max_length=3, default="MXN")
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)

    payment_form = models.CharField(max_length=2, default="99")  # Por definir
    payment_method = models.CharField(max_length=3, default="PUE")

    # Cliente (solo aplica si es tipo Ingreso)
    customer = models.ForeignKey(
        "customers.Client",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="cartas_porte",
    )

    # --- Encabezado Carta Porte (operativo) ---
    fecha_salida = models.DateTimeField(default=timezone.now)
    fecha_llegada = models.DateTimeField(default=timezone.now)
    orden = models.CharField(max_length=50, blank=True)

    itrn_us_entry = models.CharField("ITRN US entry", max_length=80, blank=True)
    pedimento = models.CharField(max_length=50, blank=True)

    # subtotal viene del viaje/ruta (snapshot); se guarda para dejar evidencia
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    # editables
    iva = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    retencion = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    observations = models.TextField(
        blank=True,
        verbose_name="Observaciones",
    )

    # --- Datos del timbrado ---
    uuid = models.CharField(max_length=100, blank=True, null=True)
    pdf_url = models.URLField(blank=True, null=True)
    xml_url = models.URLField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    last_error = models.TextField(blank=True, null=True)

    # Snapshots JSON
    payload_snapshot = models.JSONField(blank=True, null=True)   # lo que enviaste a FacturAPI
    response_snapshot = models.JSONField(blank=True, null=True)  # lo que regresó FacturAPI

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Carta Porte CFDI"
        verbose_name_plural = "Cartas Porte CFDI"

    def __str__(self):
        return f"CFDI Carta Porte del viaje {self.trip_id} - {self.uuid or self.status}"

    def sync_subtotal_from_trip(self):
        """
        Snapshot: el subtotal debe venir del viaje (tarifa_cliente_snapshot).
        """
        if self.trip_id:
            self.subtotal = self.trip.total_cobro_cliente or Decimal("0.00")

    def compute_total(self):
        """
        Regla sugerida: total = subtotal + iva - retencion
        """
        self.total = (self.subtotal or 0) + (self.iva or 0) - (self.retencion or 0)

    def save(self, *args, **kwargs):
        # fuerza subtotal (snapshot)
        self.sync_subtotal_from_trip()
        # recalcula total (si quieres que sea siempre consistente)
        self.compute_total()
        super().save(*args, **kwargs)



class CartaPorteGoods(models.Model):
    carta_porte = models.ForeignKey(
        CartaPorteCFDI,
        on_delete=models.CASCADE,
        related_name="goods",
    )
    mercancia = models.ForeignKey(
        "goods.Mercancia",
        null=True,
        blank=True,
        on_delete=models.PROTECT,   # o SET_NULL si prefieres permitir borrado lógico
        related_name="carta_porte_goods",
    )
    cantidad = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    unidad = models.CharField(max_length=50, blank=True, null=True)
    embalaje = models.CharField(max_length=10, blank=True, null=True)
    peso_en_kg = models.DecimalField(max_digits=14, decimal_places=3, blank=True, null=True)

    valor_mercancia = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    moneda = models.CharField(max_length=3, blank=True, null=True)  # ej: MXN, USD

    pedimento = models.CharField(max_length=40, blank=True, null=True)

class CartaPorteLocation(models.Model):
    TYPE_CHOICES = [
        ("Origen", "Origen"),
        ("Destino", "Destino"),
        ("Escala", "Escala intermedia"),
    ]

    carta_porte = models.ForeignKey(
        CartaPorteCFDI,
        on_delete=models.CASCADE,
        related_name="locations",
    )

    tipo_ubicacion = models.CharField(max_length=10, choices=TYPE_CHOICES)

    # Campos mínimos SAT
    rfc = models.CharField(max_length=13)
    nombre = models.CharField(max_length=255, blank=True, null=True)
    num_reg_id_trib = models.CharField(max_length=40, blank=True, null=True)
    residencia_fiscal = models.CharField(max_length=3, blank=True, null=True)

    calle = models.CharField(max_length=100, blank=True, null=True)
    numero_exterior = models.CharField(max_length=20, blank=True, null=True)
    numero_interior = models.CharField(max_length=20, blank=True, null=True)
    colonia = models.CharField(max_length=100, blank=True, null=True)
    localidad = models.CharField(max_length=100, blank=True, null=True)
    referencia = models.CharField(max_length=255, blank=True, null=True)
    municipio = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=3, blank=True, null=True)
    pais = models.CharField(max_length=3, default="MEX")
    codigo_postal = models.CharField(max_length=10)
    distancia_recorrida_km = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    orden = models.PositiveIntegerField(default=0)  # para ordenar origen, escalas, destino

    class Meta:
        ordering = ["orden"]

class CartaPorteItem(models.Model):
    carta_porte = models.ForeignKey(
        "trips.CartaPorteCFDI",
        on_delete=models.CASCADE,
        related_name="items",
    )

    cantidad = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("1.000"))
    unidad = models.CharField(max_length=20, blank=True, null=True)     # SAT: H87, KGM...
    producto = models.CharField(max_length=100, blank=True, null=True)  # SKU/Clave interna
    descripcion = models.CharField(max_length=255, blank=True, null=True)

    precio = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    descuento = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    # Impuestos por línea (porcentaje)
    iva_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("16.00"))
    ret_iva_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))

    # Calculados por línea
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    iva_monto = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    ret_iva_monto = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    importe = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden", "id"]

    def compute(self):
        qty = self.cantidad or Decimal("0")
        price = self.precio or Decimal("0")
        disc = self.descuento or Decimal("0")

        line_subtotal = (qty * price) - disc
        if line_subtotal < 0:
            line_subtotal = Decimal("0.00")

        iva_pct = (self.iva_pct or Decimal("0")) / Decimal("100")
        ret_pct = (self.ret_iva_pct or Decimal("0")) / Decimal("100")

        iva_m = line_subtotal * iva_pct
        ret_m = line_subtotal * ret_pct
        importe = line_subtotal + iva_m - ret_m

        # redondeo a 2 dec
        self.subtotal = line_subtotal.quantize(Decimal("0.01"))
        self.iva_monto = iva_m.quantize(Decimal("0.01"))
        self.ret_iva_monto = ret_m.quantize(Decimal("0.01"))
        self.importe = importe.quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        self.compute()
        super().save(*args, **kwargs)