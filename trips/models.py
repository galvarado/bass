# trips/models.py
from django.db import models

from trucks.models import Truck, ReeferBox
from operators.models import Operator
from locations.models import Location


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


class Trip(models.Model):
    """
    Un viaje con origen/destino, operador, camión y caja obligatoria.
    Permite registrar tiempos reales durante el monitoreo.
    """

    # Datos base del viaje
    origin = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="trips_as_origin",
        verbose_name="Origen",
    )
    destination = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="trips_as_destination",
        verbose_name="Destino",
    )

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

    transfer = models.CharField(
        max_length=20,
        choices=TransferType.choices,
        default=TransferType.NINGUNO,
        verbose_name="Tipo de transfer",
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

        # --- Soft delete ---
    deleted = models.BooleanField(default=False, db_index=True)

    # Managers (mismo patrón que Operator)
    objects = models.Manager()


    class Meta:
        verbose_name = "Viaje"
        verbose_name_plural = "Viajes"
        ordering = ["-id"]

    def __str__(self):
        return f"{self.origin} → {self.destination} | {self.operator} | {self.truck} + {self.reefer_box}"
