# warehouse/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Sum


# === Soft delete reutilizable (igual patrón que en workshop) ===

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


# === Catálogo de refacciones ===

class SparePart(models.Model):
    """
    Refacción en almacén.

    El stock actual NO se guarda en un campo, se calcula a partir
    de los movimientos (SparePartMovement).
    """
    code = models.CharField("Código", max_length=50, unique=True)
    name = models.CharField("Nombre", max_length=255)
    description = models.TextField("Descripción", blank=True)

    unit = models.CharField(
        "Unidad de medida",
        max_length=20,
        default="pieza",
        help_text="Ej. pieza, litro, juego, etc.",
    )

    min_stock = models.DecimalField(
        "Stock mínimo",
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Alerta si el stock actual baja de este valor.",
    )

    notes = models.TextField("Notas", blank=True)

    # Auditoría / soft delete
    created_at = models.DateTimeField("Creado en", auto_now_add=True)
    updated_at = models.DateTimeField("Actualizado en", auto_now=True)
    deleted = models.BooleanField(default=False, db_index=True)

    objects = models.Manager()
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        verbose_name = "Refacción"
        verbose_name_plural = "Refacciones"
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def soft_delete(self, using=None, keep_parents=False):
        if not self.deleted:
            self.deleted = True
            self.save(update_fields=["deleted"])

    @property
    def stock_actual(self):
        """
        Stock actual calculado como suma de todos los movimientos no borrados.
        Se espera que las entradas tengan cantidad positiva y las salidas negativa.
        """
        total = self.movements.filter(deleted=False).aggregate(
            total=Sum("quantity")
        )["total"] or 0
        return total


# === Cabecera de compra de refacciones ===

class SparePartPurchase(models.Model):
    """
    Cabecera de una compra de refacciones.

    El detalle está en SparePartPurchaseItem.
    Los movimientos de inventario se registran en SparePartMovement
    (tipo = PURCHASE), uno por cada item.
    """
    supplier_name = models.CharField("Proveedor", max_length=255)
    invoice_number = models.CharField("Factura / Folio", max_length=100, blank=True)
    date = models.DateField("Fecha de compra")

    notes = models.TextField("Notas", blank=True)

    created_at = models.DateTimeField("Creado en", auto_now_add=True)
    updated_at = models.DateTimeField("Actualizado en", auto_now=True)
    deleted = models.BooleanField(default=False, db_index=True)

    objects = SoftDeleteManager()
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        verbose_name = "Compra de refacciones"
        verbose_name_plural = "Compras de refacciones"
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"Compra #{self.id} - {self.supplier_name} ({self.date})"

    @property
    def total(self):
        return sum((item.subtotal for item in self.items.all()), 0)


class SparePartPurchaseItem(models.Model):
    """
    Partida de una compra de refacciones.
    """
    purchase = models.ForeignKey(
        SparePartPurchase,
        verbose_name="Compra",
        related_name="items",
        on_delete=models.PROTECT,
    )
    spare_part = models.ForeignKey(
        SparePart,
        verbose_name="Refacción",
        related_name="purchase_items",
        on_delete=models.PROTECT,
    )

    quantity = models.DecimalField(
        "Cantidad",
        max_digits=10,
        decimal_places=2,
    )
    unit_price = models.DecimalField(
        "Precio unitario",
        max_digits=12,
        decimal_places=2,
    )

    notes = models.CharField("Notas", max_length=255, blank=True)

    created_at = models.DateTimeField("Creado en", auto_now_add=True)
    updated_at = models.DateTimeField("Actualizado en", auto_now=True)
    deleted = models.BooleanField(default=False, db_index=True)

    objects = SoftDeleteManager()
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        verbose_name = "Partida de compra"
        verbose_name_plural = "Partidas de compra"

    def __str__(self):
        return f"{self.spare_part} x {self.quantity} ({self.purchase})"

    @property
    def subtotal(self):
        return (self.quantity or 0) * (self.unit_price or 0)


# === Movimientos de inventario ===

class SparePartMovement(models.Model):
    """
    Movimiento de inventario de una refacción.

    Registra:
    - carga inicial
    - compras
    - ajustes de inventario
    - consumo en órdenes de taller

    Convención:
    - quantity > 0  → ENTRADA a almacén
    - quantity < 0  → SALIDA de almacén
    """

    MOVEMENT_TYPES = [
        ("INITIAL", "Carga inicial"),
        ("PURCHASE", "Compra"),
        ("WORKSHOP_USAGE", "Consumo en orden de taller"),
        ("ADJUST_IN", "Ajuste de entrada"),
        ("ADJUST_OUT", "Ajuste de salida"),
    ]

    spare_part = models.ForeignKey(
        SparePart,
        verbose_name="Refacción",
        related_name="movements",
        on_delete=models.PROTECT,
    )

    movement_type = models.CharField(
        "Tipo de movimiento",
        max_length=20,
        choices=MOVEMENT_TYPES,
    )

    # Positivo para entradas, negativo para salidas
    quantity = models.DecimalField(
        "Cantidad",
        max_digits=10,
        decimal_places=2,
    )

    unit_cost = models.DecimalField(
        "Costo unitario",
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Opcional. Útil para valuación de inventario.",
    )

    # En caso de que el movimiento venga de una compra
    purchase_item = models.ForeignKey(
        SparePartPurchaseItem,
        verbose_name="Partida de compra origen",
        related_name="stock_movements",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )

    # En caso de que sea consumo en orden de taller
    workshop_order = models.ForeignKey(
        "workshop.WorkshopOrder",
        verbose_name="Orden de taller",
        related_name="spare_part_movements",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )

    description = models.CharField("Descripción", max_length=255, blank=True)

    date = models.DateTimeField("Fecha/hora", auto_now_add=True)

    created_at = models.DateTimeField("Creado en", auto_now_add=True)
    updated_at = models.DateTimeField("Actualizado en", auto_now=True)
    deleted = models.BooleanField(default=False, db_index=True)

    objects = SoftDeleteManager()
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        verbose_name = "Movimiento de refacción"
        verbose_name_plural = "Movimientos de refacciones"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.get_movement_type_display()} {self.quantity} de {self.spare_part}"

    def clean(self):
        super().clean()

        if not self.quantity or self.quantity == 0:
            raise ValidationError("La cantidad del movimiento debe ser distinta de cero.")

        # Reglas sobre el origen
        if self.movement_type == "WORKSHOP_USAGE" and self.workshop_order is None:
            raise ValidationError(
                "Los movimientos de tipo 'Consumo en orden de taller' deben tener una orden de taller asociada."
            )

        if self.movement_type == "PURCHASE" and self.purchase_item is None:
            raise ValidationError(
                "Los movimientos de tipo 'Compra' deben tener una partida de compra asociada."
            )

        # Reglas de signo sugeridas (no obligatorias, pero ayudan)
        if self.movement_type in ("WORKSHOP_USAGE", "ADJUST_OUT") and self.quantity > 0:
            raise ValidationError(
                "Para salidas (consumo o ajuste de salida) la cantidad debe ser negativa."
            )

        if self.movement_type in ("INITIAL", "PURCHASE", "ADJUST_IN") and self.quantity < 0:
            raise ValidationError(
                "Para entradas (inicial, compra o ajuste de entrada) la cantidad debe ser positiva."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
