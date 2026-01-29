# trips/models.py
from django.db import models
from customers.models import Client
from trucks.models import Truck, ReeferBox
from operators.models import Operator
from locations.models import Location, Route
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

    observations = models.TextField(
        blank=True,
        verbose_name="Observaciones",
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

    fecha_hora_salida_llegada = models.DateTimeField()
    distancia_recorrida_km = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    orden = models.PositiveIntegerField(default=0)  # para ordenar origen, escalas, destino

    class Meta:
        ordering = ["orden"]

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
    bienes_transp = models.CharField(max_length=8)   # clave producto SAT para CP
    descripcion = models.CharField(max_length=255)
    clave_unidad = models.CharField(max_length=5)   # clave unidad SAT
    unidad = models.CharField(max_length=50, blank=True, null=True)

    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    peso_en_kg = models.DecimalField(max_digits=14, decimal_places=3, blank=True, null=True)

    # opcionales
    material_peligroso = models.BooleanField(default=False)
    clave_material_peligroso = models.CharField(max_length=4, blank=True, null=True)
    embalaje = models.CharField(max_length=3, blank=True, null=True)

class CartaPorteTransportFigure(models.Model):
    ROLE_CHOICES = [
        ("01", "Operador"),
        ("02", "Propietario"),
        ("03", "Arrendatario"),
        ("04", "Notificado"),
    ]

    carta_porte = models.ForeignKey(
        CartaPorteCFDI,
        on_delete=models.CASCADE,
        related_name="figures",
    )

    tipo_figura = models.CharField(max_length=2, choices=ROLE_CHOICES)
    rfc = models.CharField(max_length=13)
    nombre = models.CharField(max_length=255)
    num_licencia = models.CharField(max_length=40, blank=True, null=True)
