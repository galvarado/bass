from django.db import models
from django.utils import timezone
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
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="locations",
        verbose_name="Cliente"
    )
    nombre = models.CharField(max_length=150, verbose_name="Nombre de la ubicación")

    # Dirección
    calle = models.CharField(max_length=150, blank=True)
    no_ext = models.CharField(max_length=30, blank=True)
    colonia = models.CharField(max_length=120, blank=True)
    colonia_sat = models.CharField(max_length=120, blank=True)
    municipio = models.CharField(max_length=120, blank=True)
    estado = models.CharField(max_length=120, blank=True)
    pais = models.CharField(max_length=80, default="México", blank=True)
    cp = models.CharField(max_length=10, blank=True)
    poblacion = models.CharField(max_length=120, blank=True)

    # Contacto
    contacto = models.CharField(max_length=120, blank=True)
    telefono = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)

    # Geo
    referencias = models.TextField(
        blank=True,
        help_text="Indicaciones de acceso, referencias de calle, etc."
    )
    horario = models.CharField(max_length=140, blank=True)

    # Estado / housekeeping
    deleted = models.BooleanField(default=False)

    # Managers
    objects = LocationManager()
    all_objects = LocationQuerySet.as_manager()

    class Meta:
        verbose_name = "Ubicación"
        verbose_name_plural = "Ubicaciones"
        ordering = ["client__nombre", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["client", "nombre"], name="uniq_location_name_per_client"),
        ]

    def __str__(self):
        return f"{self.nombre} · {self.client.nombre}"

    @property
    def full_address(self):
        parts = [
            self.calle,
            self.no_ext,
            self.colonia,
            self.municipio,
            self.estado,
            self.cp,
            self.pais,
        ]
        return ", ".join([p for p in parts if p])
