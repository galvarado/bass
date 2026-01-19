# workshop/models.py
from django.db import models
from django.core.exceptions import ValidationError


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

    def with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)

    def deleted_only(self):
        return self.with_deleted().dead()


class WorkshopOrder(models.Model):
    ESTADO_CHOICES = [
        ("ABIERTA", "Abierta"),
        ("REPARACION", "En reparación"),
        ("ESPERA_REFACCION", "En espera de refacción"),
        ("TERMINADA", "Terminada"),
        ("CANCELADA", "Cancelada"),
    ]

    estado = models.CharField(
        "Estado",
        max_length=20,
        choices=ESTADO_CHOICES,
        default="ABIERTA",
        db_index=True,
    )

    # ===== Identificación =====
    # Usaremos el id autoincremental como folio interno.
    # Si luego quieres un formato tipo OT-000123, se puede exponer con una property.

    # Puede ser camión o caja (uno u otro)
    truck = models.ForeignKey(
        "trucks.Truck",
        verbose_name="Camión",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="ordenes_taller",
    )
    reefer_box = models.ForeignKey(
        "trucks.ReeferBox",   # ajusta si tu modelo está en otra app
        verbose_name="Caja",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="ordenes_taller",
    )

    # ===== Fechas =====
    fecha_entrada = models.DateTimeField("Fecha de entrada", auto_now_add=True)
    fecha_salida_estimada = models.DateField(
        "Fecha de salida estimada",
        blank=True,
        null=True,
    )
    fecha_salida_real = models.DateTimeField(
        "Fecha de salida real",
        blank=True,
        null=True,
    )

    descripcion = models.TextField("Descripción", blank=True)


    # ===== Costos =====
    costo_mano_obra = models.DecimalField(
        "Costo mano de obra",
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )
    otros_costos = models.DecimalField(
        "Otros costos",
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )

    # ===== Meta / auditoría =====
    notas_internas = models.TextField("Notas ", blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # Soft delete
    deleted = models.BooleanField(default=False, db_index=True)

    # Managers
    objects = models.Manager()
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        verbose_name = "Orden de taller"
        verbose_name_plural = "Órdenes de taller"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"OT {self.folio_interno} - {self.unidad_display}"

    # ===== Identificador interno legible =====
    @property
    def folio_interno(self):
        # Usa el id incremental como folio interno
        return self.id

    # ===== Lógica de unidad =====
    @property
    def unidad(self):
        """Devuelve el objeto Truck o ReeferBox asociado."""
        return self.truck or self.reefer_box

    @property
    def unidad_display(self):
        """Texto legible de la unidad (económico + placas)."""
        u = self.unidad
        if not u:
            return "Sin unidad"
        return f"{u.numero_economico} ({getattr(u, 'placas', 'sin placas') or 'sin placas'})"

    def clean(self):
        """
        Reglas:
        - Debe existir EXACTAMENTE una unidad (camión XOR caja).
        """
        super().clean()

        has_truck = self.truck is not None
        has_box = self.reefer_box is not None

        if has_truck and has_box:
            raise ValidationError("Solo puedes asignar un camión O una caja, no ambos.")

        if not has_truck and not has_box:
            raise ValidationError("Debes asignar un camión o una caja a la orden de taller.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    # --- Soft delete individual ---
    def soft_delete(self, using=None, keep_parents=False):
        if not self.deleted:
            self.deleted = True
            self.save(update_fields=["deleted"])

class MaintenanceRequest(models.Model):
    ESTADO_CHOICES = [
        ("ABIERTA", "Abierta"),
        ("CONVERTIDA", "Convertida a orden de taller"),
        ("CANCELADA", "Cancelada"),
    ]

    estado = models.CharField(
        "Estado",
        max_length=20,
        choices=ESTADO_CHOICES,
        default="ABIERTA",
        db_index=True,
    )

    # ===== Unidad (camión o caja) =====
    truck = models.ForeignKey(
        "trucks.Truck",
        verbose_name="Camión",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="solicitudes_mantenimiento",
    )
    reefer_box = models.ForeignKey(
        "trucks.ReeferBox",
        verbose_name="Caja",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="solicitudes_mantenimiento",
    )

    # ===== Quién la reporta =====
    operador = models.ForeignKey(
        "operators.Operator",
        verbose_name="Operador",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="solicitudes_mantenimiento",
        help_text="Operador que reporta la solicitud (si aplica)",
    )

    # ===== Información =====
    descripcion = models.TextField("Descripción del problema")

    # ===== Conversión a orden =====
    orden_taller = models.OneToOneField(
        "workshop.WorkshopOrder",
        verbose_name="Orden de taller generada",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="solicitud_origen",
    )

    # ===== Meta =====
    notas_internas = models.TextField("Notas internas", blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # Soft delete
    deleted = models.BooleanField(default=False, db_index=True)

    objects = models.Manager()
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        verbose_name = "Solicitud de mantenimiento"
        verbose_name_plural = "Solicitudes de mantenimiento"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"SM {self.id} - {self.unidad_display}"

    # ===== Unidad =====
    @property
    def unidad(self):
        return self.truck or self.reefer_box

    @property
    def unidad_display(self):
        u = self.unidad
        if not u:
            return "Sin unidad"
        return f"{u.numero_economico} ({getattr(u, 'placas', 'sin placas') or 'sin placas'})"

    # ===== Validaciones =====
    def clean(self):
        super().clean()

        has_truck = self.truck is not None
        has_box = self.reefer_box is not None

        if has_truck and has_box:
            raise ValidationError("Solo puedes asignar un camión O una caja.")

        if not has_truck and not has_box:
            raise ValidationError("Debes asignar un camión o una caja.")

        if self.orden_taller and self.estado != "CONVERTIDA":
            raise ValidationError(
                "Si existe una orden de taller asociada, el estado debe ser CONVERTIDA."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    # ===== Acciones de dominio =====
    def convertir_a_orden(self, orden):
        """
        Vincula esta solicitud con una orden de taller existente.
        """
        if self.orden_taller:
            raise ValidationError("Esta solicitud ya fue convertida.")

        self.orden_taller = orden
        self.estado = "CONVERTIDA"
        self.save(update_fields=["orden_taller", "estado"])