from django.db import models
from django.utils import timezone
from customers.models import Client
from decimal import Decimal
from django.core.exceptions import ValidationError
from customers.models import Client

class LocationQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted=False)

    def deleted_only(self):
        return self.filter(deleted=True)


class LocationManager(models.Manager):
    def get_queryset(self):
        return LocationQuerySet(self.model, using=self._db).alive()

    def deleted_only(self):
        return self.get_queryset().deleted_only()

    def all_objects(self):
        return LocationQuerySet(self.model, using=self._db)


class Location(models.Model):
    COUNTRY_CHOICES = [
        ("MX", "México"),
        ("US", "Estados Unidos"),
    ]

    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="locations", verbose_name="Cliente"
    )
    nombre = models.CharField(max_length=150, verbose_name="Nombre de la ubicación")

    calle = models.CharField(max_length=150, blank=True)
    no_ext = models.CharField(max_length=30, blank=True)

    colonia = models.CharField(max_length=120, blank=True)
    colonia_sat = models.CharField(max_length=120, blank=True)

    municipio = models.CharField(max_length=120, blank=True)
    estado = models.CharField(max_length=120, blank=True)

    pais = models.CharField(max_length=2, choices=COUNTRY_CHOICES, default="MX")
    cp = models.CharField(max_length=10, blank=True)
    poblacion = models.CharField(max_length=120, blank=True)

    contacto = models.CharField(max_length=120, blank=True)
    telefono = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)

    referencias = models.TextField(blank=True, help_text="Indicaciones de acceso, referencias de calle, etc.")
    horario = models.CharField(max_length=140, blank=True)

    deleted = models.BooleanField(default=False)

    objects = models.Manager()
    all_objects = LocationQuerySet.as_manager()

    @property
    def country_display(self):
        return dict(self.COUNTRY_CHOICES).get(self.pais, self.pais)

    @property
    def full_address(self):
        parts = [
            self.calle,
            self.no_ext,
            self.colonia,
            self.municipio,
            self.estado,
            self.cp,
            self.country_display,
        ]
        return ", ".join([p for p in parts if p])

    def soft_delete(self):
        if not self.deleted:
            self.deleted = True
            self.save(update_fields=["deleted"])


class RouteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted=False)

    def deleted_only(self):
        return self.filter(deleted=True)


class RouteManager(models.Manager):
    def get_queryset(self):
        return RouteQuerySet(self.model, using=self._db).alive()

    def deleted_only(self):
        return self.get_queryset().deleted_only()

    def all_objects(self):
        return RouteQuerySet(self.model, using=self._db)


class Route(models.Model):
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="routes", verbose_name="Cliente"
    )

    origen = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="routes_as_origin", verbose_name="Origen"
    )
    destino = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="routes_as_destination", verbose_name="Destino"
    )

    nombre = models.CharField(
        max_length=150,
        blank=True,
        help_text="Opcional: nombre comercial (ej. GDL → CDMX). Si se deja vacío, se genera en display."
    )

    

    # Commercial terms (what you charge)
    tarifa_cliente = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        help_text="Monto que se cobra al cliente por esta ruta (base)."
    )
   
    # Operator pay (what you pay the operator)
    pago_operador = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        help_text="Monto que se paga al operador por esta ruta (base)."
    )
  

    notas = models.TextField(blank=True)

    deleted = models.BooleanField(default=False)

    objects = models.Manager()                 # ← NO filtra
    all_objects = RouteQuerySet.as_manager()

    class Meta:
        verbose_name = "Ruta"
        verbose_name_plural = "Rutas"
        ordering = ["client__nombre", "origen__nombre", "destino__nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["client", "origen", "destino"],
                name="uniq_route_per_client_origin_dest"
            ),
        ]

    def soft_delete(self):
        if not self.deleted:
            self.deleted = True
            self.save(update_fields=["deleted"])

    def clean(self):
        # Prevent cross-client mismatch
        if self.origen_id and self.client_id and self.origen.client_id != self.client_id:
            raise ValidationError({"origen": "El origen no pertenece a este cliente."})
        if self.destino_id and self.client_id and self.destino.client_id != self.client_id:
            raise ValidationError({"destino": "El destino no pertenece a este cliente."})
        if self.origen_id and self.destino_id and self.origen_id == self.destino_id:
            raise ValidationError("Origen y destino no pueden ser la misma ubicación.")

    def __str__(self):
        return f"{self.display_name} · {self.client.nombre}"
        

    @property
    def display_name(self):
        if self.nombre:
            return self.nombre
        return f"{self.origen.nombre} → {self.destino.nombre}"
