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

    # Catálogos https://www.cloudb.sat.gob.mx/datos_fiscales/regimen
    REGIMEN_FISCAL_CHOICES = [
        ('601', '601 - Régimen General de Ley Personas Morales'),
        ('602', '602 - Régimen Simplificado de Ley Personas Morales'),
        ('603', '603 - Personas Morales con Fines no Lucrativos'),
        ('604', '604 - Régimen de Pequeños Contribuyentes'),
        ('605', '605 - Sueldos y Salarios e Ingresos Asimilados a Salarios'),
        ('606', '606 - Régimen de Arrendamiento'),
        ('607', '607 - Régimen de Enajenación o Adquisición de Bienes'),
        ('608', '608 - Régimen de los Demás Ingresos'),
        ('609', '609 - Régimen de Consolidación'),
        ('610', '610 - Residentes en el Extranjero sin Establecimiento Permanente en México'),
        ('611', '611 - Ingresos por Dividendos (Socios y Accionistas)'),
        ('612', '612 - Personas Físicas con Actividades Empresariales y Profesionales'),
        ('613', '613 - Régimen Intermedio de las Personas Físicas con Actividades Empresariales'),
        ('614', '614 - Ingresos por Intereses'),
        ('615', '615 - Ingresos por Obtención de Premios'),
        ('616', '616 - Sin Obligaciones Fiscales'),
        ('617', '617 - PEMEX'),
        ('618', '618 - Régimen Simplificado de Ley Personas Físicas'),
        ('619', '619 - Ingresos por la Obtención de Préstamos'),
        ('620', '620 - Sociedades Cooperativas de Producción que Optan por Diferir sus Ingresos'),
        ('621', '621 - Régimen de Incorporación Fiscal'),
        ('622', '622 - Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras (PM)'),
        ('623', '623 - Régimen Opcional para Grupos de Sociedades'),
        ('624', '624 - Régimen de los Coordinados'),
        ('625', '625 - Actividades Empresariales con Ingresos a través de Plataformas Tecnológicas'),
        ('626', '626 - Régimen Simplificado de Confianza'),
    ]

    USO_CFDI_CHOICES = [
        # ===== GASTOS =====
        ('G01', 'G01 - Adquisición de mercancías'),
        ('G02', 'G02 - Devoluciones, descuentos o bonificaciones'),
        ('G03', 'G03 - Gastos en general'),

        # ===== INVERSIONES =====
        ('I01', 'I01 - Construcciones'),
        ('I02', 'I02 - Mobiliario y equipo de oficina por inversiones'),
        ('I03', 'I03 - Equipo de transporte'),
        ('I04', 'I04 - Equipo de cómputo y accesorios'),
        ('I05', 'I05 - Dados, troqueles, moldes, matrices y herramental'),
        ('I06', 'I06 - Comunicaciones telefónicas'),
        ('I07', 'I07 - Comunicaciones satelitales'),
        ('I08', 'I08 - Otra maquinaria y equipo'),

        # ===== DEDUCCIONES PERSONALES (PF) =====
        ('D01', 'D01 - Honorarios médicos, dentales y hospitalarios'),
        ('D02', 'D02 - Gastos médicos por incapacidad o discapacidad'),
        ('D03', 'D03 - Gastos funerales'),
        ('D04', 'D04 - Donativos'),
        ('D05', 'D05 - Intereses reales pagados por créditos hipotecarios'),
        ('D06', 'D06 - Aportaciones voluntarias al SAR'),
        ('D07', 'D07 - Primas por seguros de gastos médicos'),
        ('D08', 'D08 - Gastos de transportación escolar obligatoria'),
        ('D09', 'D09 - Depósitos en cuentas para el ahorro / planes de pensiones'),
        ('D10', 'D10 - Pagos por servicios educativos (colegiaturas)'),

        # ===== OTROS =====
        ('S01', 'S01 - Sin efectos fiscales'),
        ('CP01', 'CP01 - Pagos'),
        ('CN01', 'CN01 - Nómina'),
    ]

    FORMA_PAGO_CHOICES = [
        ('01', '01 - Efectivo'),
        ('02', '02 - Cheque'),
        ('03', '03 - Transferencia'),
        ('04', '04 - Tarjetas de crédito'),
        ('05', '05 - Monederos electrónicos'),
        ('06', '06 - Dinero electrónico'),
        ('07', '07 - Tarjetas digitales'),
        ('08', '08 - Vales de despensa'),
        ('09', '09 - Bienes'),
        ('10', '10 - Servicio'),
        ('11', '11 - Por cuenta de tercero'),
        ('12', '12 - Dación en pago'),
        ('13', '13 - Pago por subrogación'),
        ('14', '14 - Pago por consignación'),
        ('15', '15 - Condenación'),
        ('16', '16 - Cancelación'),
        ('17', '17 - Compensación'),
        ('98', '98 - N/A'),
        ('99', '99 - Otros'),
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
