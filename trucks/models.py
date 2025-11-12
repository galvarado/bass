# trucks/models.py
from django.db import models


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        # Soft delete en lote
        return super().update(deleted=True)

    def hard_delete(self):
        # Borrado físico
        return super().delete()

    def alive(self):
        return self.filter(deleted=False)

    def dead(self):
        return self.filter(deleted=True)


class SoftDeleteManager(models.Manager):
    """Devuelve SOLO registros no eliminados por defecto."""
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(deleted=False)

    # Accesos convenientes
    def with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)

    def deleted_only(self):
        return self.with_deleted().dead()


class Truck(models.Model):
    # ===== Datos generales =====
    nombre = models.CharField("Nombre", max_length=15, unique=True)
    placas = models.CharField("Placas", max_length=15, unique=True)
    numero_economico = models.CharField("Número económico", max_length=20, unique=True)
    serie = models.CharField("Serie (VIN)", max_length=50, blank=True, null=True)
    marca = models.CharField("Marca", max_length=50, blank=True, null=True)

    # ===== Especificaciones =====
    motor = models.CharField("Motor", max_length=80, blank=True, null=True)
    combustible = models.CharField("Combustible", max_length=30, blank=True, null=True)
    capacidad_combustible = models.DecimalField(
        "Capacidad de combustible (L)", max_digits=7, decimal_places=2, blank=True, null=True
    )
    peso_bruto = models.DecimalField("Peso bruto (kg)", max_digits=10, decimal_places=2, blank=True, null=True)
    categoria = models.CharField("Categoría", max_length=50, blank=True, null=True)
    rin = models.CharField("Rin", max_length=30, blank=True, null=True)

    # ===== Operación / visibilidad =====
    ciclo_mtto = models.CharField("Ciclo Mtto", max_length=100, blank=True, null=True)

    # ===== Documentos =====
    seguro = models.CharField("Seguro (póliza/folio)", max_length=100, blank=True, null=True)
    tarjeta_circulacion = models.CharField("Tarjeta de circulación", max_length=100, blank=True, null=True)
    iave = models.CharField("IAVE", max_length=100, blank=True, null=True)

    # ===== Soft delete =====
    deleted = models.BooleanField(default=False, db_index=True)

    # Managers
    objects = models.Manager()       
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        verbose_name = "Camión"
        verbose_name_plural = "Camiones"
        ordering = ["numero_economico"]

    def __str__(self):
        return f"{self.numero_economico} ({self.placas})"

    # --- Métodos de instancia ---
    def soft_delete(self, using=None, keep_parents=False):
        """Soft delete individual."""
        if not self.deleted:
            self.deleted = True
            self.save(update_fields=["deleted"])

# reeferboxes/models.py
from django.db import models


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        # Soft delete en lote
        return super().update(deleted=True)

    def hard_delete(self):
        # Borrado físico
        return super().delete()

    def alive(self):
        return self.filter(deleted=False)

    def dead(self):
        return self.filter(deleted=True)


class SoftDeleteManager(models.Manager):
    """Devuelve SOLO registros no eliminados por defecto."""
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(deleted=False)

    # Accesos convenientes
    def with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)

    def deleted_only(self):
        return self.with_deleted().dead()


class ReeferBox(models.Model):
    # ===== Datos generales =====
    nombre = models.CharField("Nombre", max_length=15, unique=True)
    categoria = models.CharField("Categoría", max_length=50, blank=True, null=True)
    numero_economico = models.CharField("Número económico", max_length=20, unique=True)
    modelo = models.CharField("Modelo", max_length=50, blank=True, null=True)
    marca = models.CharField("Marca", max_length=50, blank=True, null=True)
    numero_serie = models.CharField("Número de serie", max_length=50, blank=True, null=True)
    placas = models.CharField("Placas", max_length=15, unique=True, blank=True, null=True)

    # ===== Especificaciones =====
    km = models.DecimalField("Kilometraje", max_digits=10, decimal_places=2, blank=True, null=True)
    ciclo_mtto = models.CharField("Ciclo Mtto", max_length=100, blank=True, null=True)
    rin = models.CharField("Rin", max_length=30, blank=True, null=True)
    peso_bruto = models.DecimalField("Peso bruto (kg)", max_digits=10, decimal_places=2, blank=True, null=True)
    combustible = models.CharField("Combustible", max_length=30, blank=True, null=True)
    capacidad_thermo = models.DecimalField(
        "Capacidad de Thermo (BTU o HP)", max_digits=10, decimal_places=2, blank=True, null=True
    )
    tipo_remolque = models.CharField("Tipo de remolque", max_length=50, blank=True, null=True)

    # ===== Documentos =====
    seguro = models.CharField("Seguro (póliza/folio)", max_length=100, blank=True, null=True)
    tarjeta_circulacion = models.CharField("Tarjeta de circulación", max_length=100, blank=True, null=True)


    # ===== Soft delete =====
    deleted = models.BooleanField(default=False, db_index=True)

    # Managers
    objects = models.Manager()       
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        verbose_name = "Caja refrigerada"
        verbose_name_plural = "Cajas refrigeradas"
        ordering = ["numero_economico"]

    def __str__(self):
        return f"{self.numero_economico} ({self.placas or 'sin placas'})"

    # --- Métodos de instancia ---
    def soft_delete(self, using=None, keep_parents=False):
        """Soft delete individual."""
        if not self.deleted:
            self.deleted = True
            self.save(update_fields=["deleted"])
