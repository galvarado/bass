# warehouse/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Sum
from suppliers.models import Supplier


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

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        SUBMITTED = "SUBMITTED", "Enviada a aprobación"
        APPROVED = "APPROVED", "Aprobada"
        REJECTED = "REJECTED", "Rechazada"
        
    supplier = models.ForeignKey(
        Supplier,
        verbose_name="Proveedor",
        related_name="spare_part_purchases",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        help_text="Proveedor registrado en el catálogo."
    )
    invoice_number = models.CharField("Factura / Folio", max_length=100, blank=True)
    date = models.DateField("Fecha de compra")
    status = models.CharField(
        "Estatus",
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
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
        prov = (self.supplier.razon_social or self.supplier.nombre) if self.supplier else "—"
        return f"Compra #{self.id} - {prov} ({self.date})"

    @property
    def total(self):
        return sum((item.subtotal for item in self.items.all()), 0)

    @property
    def amount_paid(self):
        return self.payment_allocations.filter(deleted=False).aggregate(
            total=Sum("amount_applied")
        )["total"] or 0

    @property
    def balance(self):
        return (self.total or 0) - (self.amount_paid or 0)

    def amount_paid_excluding_allocation(self, allocation_pk=None):
        qs = self.payment_allocations.filter(deleted=False)
        if allocation_pk:
            qs = qs.exclude(pk=allocation_pk)
        return qs.aggregate(total=Sum("amount_applied"))["total"] or 0


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

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Sum
from suppliers.models import Supplier


class SupplierPayment(models.Model):
    class Method(models.TextChoices):
        TRANSFER = "TRANSFER", "Transferencia"
        CASH = "CASH", "Efectivo"
        CHECK = "CHECK", "Cheque"
        CARD = "CARD", "Tarjeta"
        OTHER = "OTHER", "Otro"

    class Status(models.TextChoices):
        POSTED = "POSTED", "Aplicado"
        VOID = "VOID", "Anulado"

    supplier = models.ForeignKey(
        Supplier,
        verbose_name="Proveedor",
        related_name="payments",
        on_delete=models.PROTECT,
        null=False,
        blank=False,
    )

    date = models.DateField("Fecha de pago")
    method = models.CharField("Método", max_length=20, choices=Method.choices, default=Method.TRANSFER)
    reference = models.CharField("Referencia", max_length=120, blank=True)
    amount = models.DecimalField("Monto", max_digits=12, decimal_places=2)

    status = models.CharField("Estatus", max_length=20, choices=Status.choices, default=Status.POSTED, db_index=True)
    notes = models.TextField("Notas", blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Creado por",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="supplier_payments_created",
    )

    created_at = models.DateTimeField("Creado en", auto_now_add=True)
    updated_at = models.DateTimeField("Actualizado en", auto_now=True)
    deleted = models.BooleanField(default=False, db_index=True)

    objects = SoftDeleteManager()
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        verbose_name = "Pago a proveedor"
        verbose_name_plural = "Pagos a proveedores"
        ordering = ["-date", "-id"]

    def __str__(self):
        prov = (self.supplier.razon_social or self.supplier.nombre) if self.supplier else "—"
        return f"Pago #{self.id} - {prov} ({self.date})"

    @property
    def applied_amount(self):
        return self.allocations.filter(deleted=False).aggregate(
            total=Sum("amount_applied")
        )["total"] or 0

    @property
    def unapplied_amount(self):
        return (self.amount or 0) - (self.applied_amount or 0)

    def clean(self):
        super().clean()
        if not self.amount or self.amount <= 0:
            raise ValidationError("El monto del pago debe ser mayor a cero.")


class SupplierPaymentAllocation(models.Model):
    """
    Aplicación de un pago a una compra específica.
    Permite pagos parciales y pagos a múltiples compras.
    """
    payment = models.ForeignKey(
        SupplierPayment,
        verbose_name="Pago",
        related_name="allocations",
        on_delete=models.PROTECT,
    )
    purchase = models.ForeignKey(
        "warehouse.SparePartPurchase",
        verbose_name="Compra",
        related_name="payment_allocations",
        on_delete=models.PROTECT,
    )

    amount_applied = models.DecimalField("Monto aplicado", max_digits=12, decimal_places=2)

    created_at = models.DateTimeField("Creado en", auto_now_add=True)
    updated_at = models.DateTimeField("Actualizado en", auto_now=True)
    deleted = models.BooleanField(default=False, db_index=True)

    objects = SoftDeleteManager()
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        verbose_name = "Aplicación de pago"
        verbose_name_plural = "Aplicaciones de pagos"
        ordering = ["-id"]

    def __str__(self):
        return f"{self.payment} -> Compra #{self.purchase_id}: {self.amount_applied}"

    def clean(self):
        super().clean()

        amt = self.amount_applied or Decimal("0.00")
        if amt <= 0:
            return

        # ✅ 1) Validar saldo de la compra (ejemplo)
        if self.purchase_id:
            if amt > (self.purchase.balance or Decimal("0.00")):
                raise ValidationError({"amount_applied": "El monto aplicado excede el saldo de la compra."})

        # ✅ 2) Evitar duplicar compra en el MISMO pago
        # (esto es lo que te está tronando)
        if not self.purchase_id:
            return

        payment_id = self.payment_id  # ← usa el _id (no la instancia)
        if not payment_id:
            # Aún no existe el pago (inline formset en Create) => NO puedes consultar por payment
            return

        qs = SupplierPaymentAllocation.all_objects.filter(
            deleted=False,
            payment_id=payment_id,      # ✅ no payment=self.payment
            purchase_id=self.purchase_id,
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        if qs.exists():
            raise ValidationError({"purchase": "Ya existe una aplicación a esta compra dentro de este pago."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
