from django.db import models
from django.core.validators import MinValueValidator

class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        return super().update(deleted=True)

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(deleted=False)

    def dead(self):
        return self.filter(deleted=True)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(deleted=False)

    def with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)

    def deleted_only(self):
        return self.with_deleted().dead()


class Client(models.Model):
    STATUS_CHOICES = [
        ('ALTA', 'Alta'),
        ('BAJA', 'Baja'),
    ]

    # Catálogos sencillos (puedes reemplazar por catálogos SAT completos cuando gustes)
    REGIMEN_FISCAL_CHOICES = [
        ('601', '601 - General de Ley Personas Morales'),
        ('603', '603 - Personas Morales con Fines no Lucrativos'),
        ('605', '605 - Sueldos y Salarios e Ingresos Asimilados a Salarios'),
        ('612', '612 - Personas Físicas con Actividades Empresariales y Profesionales'),
        ('616', '616 - Sin obligaciones fiscales'),
        ('OTRO', 'Otro'),
    ]

    USO_CFDI_CHOICES = [
        ('G01', 'Adquisición de mercancías'),
        ('G03', 'Gastos en general'),
        ('I01', 'Construcciones'),
        ('P01', 'Por definir / N/A'),
        ('OTRO', 'Otro'),
    ]

    FORMA_PAGO_CHOICES = [
        ('EFECTIVO', 'Efectivo'),
        ('TRANSFERENCIA', 'Transferencia'),
        ('TARJETA', 'Tarjeta'),
        ('CHEQUE', 'Cheque'),
        ('PPD', 'PPD - Pago en parcialidades o diferido'),
        ('PUE', 'PUE - Pago en una sola exhibición'),
        ('OTRO', 'Otro'),
    ]

    # --- Datos Generales ---
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ALTA')

    nombre = models.CharField(max_length=120)               # Nombre comercial / display
    razon_social = models.CharField(max_length=200, blank=True, null=True)
    rfc = models.CharField(max_length=15, blank=True, null=True)
    regimen_fiscal = models.CharField(max_length=10, choices=REGIMEN_FISCAL_CHOICES, blank=True, null=True)
    id_tributario = models.CharField(max_length=30, blank=True, null=True)  # VAT/Tax ID extranjero

    # Dirección (igual que Operator)
    calle = models.CharField(max_length=120, blank=True, null=True)
    no_ext = models.CharField(max_length=10, blank=True, null=True)
    colonia = models.CharField(max_length=120, blank=True, null=True)
    colonia_sat = models.CharField(max_length=120, blank=True, null=True)
    municipio = models.CharField(max_length=120, blank=True, null=True)
    estado = models.CharField(max_length=120, blank=True, null=True)
    pais = models.CharField(max_length=80, default='México')
    cp = models.CharField(max_length=10, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    poblacion = models.CharField(max_length=100, blank=True, null=True)

    # Crédito y facturación
    limite_credito = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    dias_credito = models.PositiveSmallIntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO_CHOICES, blank=True, null=True)
    cuenta = models.CharField(max_length=30, blank=True, null=True)  # cuenta/referencia interna o bancaria
    uso_cfdi = models.CharField(max_length=10, choices=USO_CFDI_CHOICES, blank=True, null=True)

    observaciones = models.TextField(blank=True, null=True)

    # --- Soft delete ---
    deleted = models.BooleanField(default=False, db_index=True)

    # Managers (mismo patrón que Operator)
    objects = models.Manager()
    alive = SoftDeleteQuerySet.as_manager()

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['deleted']),
            models.Index(fields=['nombre']),
            models.Index(fields=['rfc']),
        ]

    def __str__(self):
        # Prioriza razón social para documentos; cae a nombre comercial si no hay
        return self.razon_social or self.nombre

    # --- Métodos de instancia ---
    def soft_delete(self, using=None, keep_parents=False):
        if not self.deleted:
            self.deleted = True
            self.save(update_fields=["deleted"])
