# operators/models.py
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


class Operator(models.Model):
    STATUS_CHOICES = [
        ('ALTA', 'Alta'),
        ('BAJA', 'Baja'),
    ]
    TIPO_CONTRATO_CHOICES = [
        ('BASE', 'Base'),
        ('TEMPORAL', 'Temporal'),
        ('HONORARIOS', 'Honorarios'),
    ]
    TIPO_REGIMEN_CHOICES = [
        ('ASALARIADO', 'Asalariado'),
        ('INDEPENDIENTE', 'Independiente'),
    ]
    TIPO_JORNADA_CHOICES = [
        ('DIURNA', 'Diurna'),
        ('NOCTURNA', 'Nocturna'),
        ('MIXTA', 'Mixta'),
    ]
    TIPO_LIQUIDACION_CHOICES = [
        ('SEMANAL', 'Semanal'),
        ('QUINCENAL', 'Quincenal'),
        ('MENSUAL', 'Mensual'),
    ]

    # --- Datos Generales ---
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ALTA')
    nombre = models.CharField(max_length=120)
    calle = models.CharField(max_length=120, blank=True, null=True)
    no_ext = models.CharField(max_length=10, blank=True, null=True)
    colonia = models.CharField(max_length=120, blank=True, null=True)
    colonia_sat = models.CharField(max_length=120, blank=True, null=True)
    municipio = models.CharField(max_length=120, blank=True, null=True)
    estado = models.CharField(max_length=120, blank=True, null=True)
    pais = models.CharField(max_length=80, default='MÉXICO')
    cp = models.CharField(max_length=10, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    rfc = models.CharField(max_length=15, blank=True, null=True)
    curp = models.CharField(max_length=18, blank=True, null=True)
    tipo_sangre = models.CharField(max_length=8, blank=True, null=True)
    imss = models.CharField(max_length=15, blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    fecha_ingreso = models.DateField(blank=True, null=True)
    puesto = models.CharField(max_length=120, blank=True, null=True)
    tipo_contrato = models.CharField(max_length=20, choices=TIPO_CONTRATO_CHOICES, blank=True, null=True)
    tipo_regimen = models.CharField(max_length=20, choices=TIPO_REGIMEN_CHOICES, blank=True, null=True)
    tipo_jornada = models.CharField(max_length=20, choices=TIPO_JORNADA_CHOICES, blank=True, null=True)
    tipo_liquidacion = models.CharField(max_length=20, choices=TIPO_LIQUIDACION_CHOICES, blank=True, null=True)
    periodicidad = models.CharField(max_length=50, blank=True, null=True)
    cuenta_bancaria = models.CharField(max_length=30, blank=True, null=True)
    cuenta = models.CharField(max_length=30, blank=True, null=True)
    poblacion = models.CharField(max_length=100, blank=True, null=True)
    sueldo_fijo = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    comision = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    tope = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    # --- Documentos ---
    ine = models.CharField(max_length=50, blank=True, null=True)
    ine_vencimiento = models.DateField(blank=True, null=True)
    licencia_federal = models.CharField(max_length=50, blank=True, null=True)
    licencia_federal_vencimiento = models.DateField(blank=True, null=True)
    visa = models.CharField(max_length=50, blank=True, null=True)
    visa_vencimiento = models.DateField(blank=True, null=True)
    pasaporte = models.CharField(max_length=50, blank=True, null=True)
    pasaporte_vencimiento = models.DateField(blank=True, null=True)
    examen_medico = models.CharField(max_length=50, blank=True, null=True)
    examen_medico_vencimiento = models.DateField(blank=True, null=True)
    rcontrol = models.CharField(max_length=50, blank=True, null=True)
    rcontrol_vencimiento = models.DateField(blank=True, null=True)
    antidoping = models.CharField(max_length=50, blank=True, null=True)
    antidoping_vencimiento = models.DateField(blank=True, null=True)

    # --- Soft delete ---
    deleted = models.BooleanField(default=False, db_index=True)

    # Managers
    objects = models.Manager()       
    alive = SoftDeleteQuerySet.as_manager()   

    class Meta:
        verbose_name = "Operador"
        verbose_name_plural = "Operadores"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    # --- Métodos de instancia ---
    def soft_delete(self, using=None, keep_parents=False):
        """Soft delete individual."""
        if not self.deleted:
            self.deleted = True
            self.save(update_fields=["deleted"])

