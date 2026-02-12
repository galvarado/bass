# settlement/models.py
from __future__ import annotations

from decimal import Decimal
from typing import Optional, Set

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from trips.models import Trip, TripStatus


# ============================================================
# EVIDENCIAS / APROBACIÓN (por TRIP)
# ============================================================

class SettlementApprovalStatus(models.TextChoices):
    DRAFT = "draft", "Borrador"
    SUBMITTED = "submitted", "Enviado"
    APPROVED = "approved", "Aprobado"
    REJECTED = "rejected", "Rechazado"


class EvidenceType(models.TextChoices):
    LOAD = "load", "Foto de la carga"
    SEAL = "seal", "Foto del sello"
    OTHER = "other", "Otro"


REQUIRED_EVIDENCE_TYPES: Set[str] = {EvidenceType.LOAD, EvidenceType.SEAL}


def settlement_evidence_upload_path(instance: "SettlementEvidence", filename: str) -> str:
    return f"settlement/trips/{instance.trip_id}/evidence/{filename}"


class SettlementEvidence(models.Model):
    """
    Evidencia (imagen) asociada a un Trip.
    Regla: se puede subir en cualquier status EXCEPTO PROGRAMADO.
    """
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name="settlement_evidences",
    )

    evidence_type = models.CharField(
        max_length=24,
        choices=EvidenceType.choices,
        default=EvidenceType.OTHER,
    )

    image = models.ImageField(upload_to=settlement_evidence_upload_path)
    notes = models.CharField(max_length=280, blank=True, default="")

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_settlement_evidences",
    )
    uploaded_at = models.DateTimeField(default=timezone.now)

    # Revisión por evidencia (opcional)
    is_valid = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_settlement_evidences",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.CharField(max_length=280, blank=True, default="")

    deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["-uploaded_at", "-id"]
        indexes = [
            models.Index(fields=["trip", "evidence_type"]),
            models.Index(fields=["trip", "deleted"]),
        ]

    def __str__(self) -> str:
        return f"Evidence #{self.id} Trip#{self.trip_id} ({self.evidence_type})"

    def clean(self):
        """
        ✅ Regla: no permitir evidencias si el viaje está PROGRAMADO.
        """
        super().clean()
        if self.trip_id and self.trip.status == TripStatus.PROGRAMADO:
            raise ValidationError("No se pueden subir evidencias mientras el viaje está en estado PROGRAMADO.")


class SettlementApproval(models.Model):
    """
    Un registro por Trip: controla el estado global de aprobación de evidencias
    (habilita usar el trip para liquidación).
    """
    trip = models.OneToOneField(
        Trip,
        on_delete=models.CASCADE,
        related_name="settlement_approval",
    )

    status = models.CharField(
        max_length=16,
        choices=SettlementApprovalStatus.choices,
        default=SettlementApprovalStatus.DRAFT,
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_settlement_approvals",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_settlement_approvals",
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    decision_notes = models.TextField(blank=True, default="")

    class Meta:
        indexes = [models.Index(fields=["status"])]

    def __str__(self) -> str:
        return f"SettlementApproval Trip#{self.trip_id} ({self.status})"

    # ---------- Helpers ----------
    def missing_required_evidence_types(self) -> set[str]:
        present = set(
            self.trip.settlement_evidences
                .filter(deleted=False)
                .values_list("evidence_type", flat=True)
        )
        return set(REQUIRED_EVIDENCE_TYPES) - present

    def can_be_approved(self) -> bool:
        return len(self.missing_required_evidence_types()) == 0

    def submit(self, user, notes: str = ""):
        missing = self.missing_required_evidence_types()
        if missing:
            missing_labels = ", ".join(dict(EvidenceType.choices).get(m, m) for m in missing)
            raise ValidationError(f"Faltan evidencias requeridas para enviar: {missing_labels}")

        self.status = SettlementApprovalStatus.SUBMITTED
        self.submitted_by = user
        self.submitted_at = timezone.now()
        if notes:
            self.decision_notes = notes
        self.save(update_fields=["status", "submitted_by", "submitted_at", "decision_notes"])

    def approve(self, user, notes: str = ""):
        if not self.can_be_approved():
            missing = self.missing_required_evidence_types()
            missing_labels = ", ".join(dict(EvidenceType.choices).get(m, m) for m in missing)
            raise ValidationError(f"No se puede aprobar. Faltan: {missing_labels}")

        self.status = SettlementApprovalStatus.APPROVED
        self.decided_by = user
        self.decided_at = timezone.now()
        if notes:
            self.decision_notes = notes
        self.save(update_fields=["status", "decided_by", "decided_at", "decision_notes"])

    def reject(self, user, notes: str = ""):
        self.status = SettlementApprovalStatus.REJECTED
        self.decided_by = user
        self.decided_at = timezone.now()
        if notes:
            self.decision_notes = notes
        self.save(update_fields=["status", "decided_by", "decided_at", "decision_notes"])


# ============================================================
# LIQUIDACIÓN (documento) + trips incluidos
# ============================================================

class SettlementStatus(models.TextChoices):
    DRAFT = "draft", "Borrador"
    READY = "ready", "Lista (aprobada)"
    PAID = "paid", "Pagada"
    CANCELED = "canceled", "Cancelada"


class SettlementTripRole(models.TextChoices):
    LOAD = "load", "Carga (ida)"
    RETURN = "return", "Baja (vuelta)"


class SettlementLineCategory(models.TextChoices):
    INGRESO = "ingreso", "Ingreso"
    ANTICIPO = "anticipo", "Anticipo / Descuento"
    GASTO = "gasto", "Gasto"
    CASETA = "caseta", "Caseta"


class OperatorSettlement(models.Model):
    """
    Documento de liquidación (formato imprimible).
    Puede incluir SOLO ida (LOAD) o ida + vuelta (RETURN).
    """
    status = models.CharField(
        max_length=16,
        choices=SettlementStatus.choices,
        default=SettlementStatus.DRAFT,
    )

    operator = models.ForeignKey(
        "operators.Operator",
        on_delete=models.PROTECT,
        related_name="settlements",
    )

    unit_label = models.CharField(max_length=32, help_text="Ej. T06")

    period_from = models.DateField()
    period_to = models.DateField()

    deposit_date = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_settlements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["operator", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Settlement #{self.id} - {self.operator} ({self.period_from}→{self.period_to})"

    # ---------- Trips incluidos ----------
    def _trip_for_role(self, role: str) -> Optional[Trip]:
        rel = self.trips.filter(role=role).select_related("trip").first()
        return rel.trip if rel else None

    @property
    def load_trip(self) -> Optional[Trip]:
        return self._trip_for_role(SettlementTripRole.LOAD)

    @property
    def return_trip(self) -> Optional[Trip]:
        return self._trip_for_role(SettlementTripRole.RETURN)

    # ---------- Totales ----------
    def _sum_lines(self, category: str) -> Decimal:
        agg = self.lines.filter(category=category).aggregate(total=models.Sum("amount"))["total"]
        return agg or Decimal("0.00")

    @property
    def ingresos_total(self) -> Decimal:
        return self._sum_lines(SettlementLineCategory.INGRESO)

    @property
    def anticipos_total(self) -> Decimal:
        return self._sum_lines(SettlementLineCategory.ANTICIPO)

    @property
    def gastos_total(self) -> Decimal:
        return self._sum_lines(SettlementLineCategory.GASTO)

    @property
    def casetas_total(self) -> Decimal:
        return self._sum_lines(SettlementLineCategory.CASETA)

    @property
    def total_a_liquidar(self) -> Decimal:
        return self.ingresos_total - self.anticipos_total - self.gastos_total - self.casetas_total

    # ---------- Validaciones de negocio ----------
    def clean(self):
        """
        - Debe existir exactamente 1 LOAD (ida) para que el documento sea válido.
        - RETURN es opcional.
        - Si está READY/PAID, forzamos que el LOAD exista.
        """
        super().clean()

        if self.period_from and self.period_to and self.period_from > self.period_to:
            raise ValidationError("El periodo 'desde' no puede ser mayor que 'hasta'.")

        # Si todavía no se guardó, no podemos validar relaciones m2m/related
        if not self.pk:
            return

        load_count = self.trips.filter(role=SettlementTripRole.LOAD).count()
        return_count = self.trips.filter(role=SettlementTripRole.RETURN).count()

        if load_count != 1:
            raise ValidationError("La liquidación debe tener exactamente 1 viaje como CARGA (ida).")

        if return_count > 1:
            raise ValidationError("La liquidación solo puede tener 0 o 1 viaje como BAJA (vuelta).")

        if self.status in (SettlementStatus.READY, SettlementStatus.PAID) and load_count != 1:
            raise ValidationError("Para marcar como LISTA/PAGADA debe existir el viaje CARGA (ida).")

    def validate_trips_ready_for_settlement(self):
        """
        Llamar antes de marcar READY:
        - Trips incluidos NO pueden estar PROGRAMADO.
        - Trips incluidos deben tener SettlementApproval APPROVED.
        """
        rels = list(self.trips.select_related("trip"))
        if not rels:
            raise ValidationError("No hay viajes ligados a esta liquidación.")

        for rel in rels:
            t = rel.trip
            if t.status == TripStatus.PROGRAMADO:
                raise ValidationError(f"El viaje #{t.id} está PROGRAMADO; no puede incluirse en liquidación.")

            # Requiere approval aprobado
            approval = getattr(t, "settlement_approval", None)
            if not approval or approval.status != SettlementApprovalStatus.APPROVED:
                raise ValidationError(f"El viaje #{t.id} no tiene evidencias aprobadas para liquidación.")


class OperatorSettlementTrip(models.Model):
    """
    Relación settlement ↔ trip con rol (LOAD obligatorio, RETURN opcional).
    """
    settlement = models.ForeignKey(
        OperatorSettlement,
        on_delete=models.CASCADE,
        related_name="trips",
    )
    trip = models.ForeignKey(
        Trip,
        on_delete=models.PROTECT,
        related_name="settlement_memberships",
    )
    role = models.CharField(
        max_length=16,
        choices=SettlementTripRole.choices,
        default=SettlementTripRole.LOAD,
    )

    class Meta:
        unique_together = [
            ("settlement", "role"),  # max 1 LOAD y max 1 RETURN por settlement
        ]
        indexes = [
            models.Index(fields=["settlement", "role"]),
            models.Index(fields=["trip"]),
        ]

    def __str__(self) -> str:
        return f"Settlement#{self.settlement_id} {self.role} Trip#{self.trip_id}"

    def clean(self):
        super().clean()

        # No permitir que el mismo trip se agregue dos veces a la misma liquidación
        if self.settlement_id and self.trip_id:
            exists = OperatorSettlementTrip.objects.filter(
                settlement_id=self.settlement_id,
                trip_id=self.trip_id,
            )
            if self.pk:
                exists = exists.exclude(pk=self.pk)
            if exists.exists():
                raise ValidationError("Este viaje ya está ligado a esta liquidación.")

        # Control de operador/unidad sugerido (si aplica en tu modelo Trip)
        # Si Trip tiene operator/truck, puedes validar consistencia aquí.
        # if self.trip_id and self.settlement_id:
        #     if self.trip.operator_id != self.settlement.operator_id:
        #         raise ValidationError("El viaje no corresponde al operador de la liquidación.")


class OperatorSettlementLine(models.Model):
    """
    Líneas / conceptos capturados en el formato:
    - INGRESOS
    - ANTICIPOS/DESCUENTOS
    - GASTOS
    - CASETAS
    """
    settlement = models.ForeignKey(
        OperatorSettlement,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    category = models.CharField(
        max_length=16,
        choices=SettlementLineCategory.choices,
    )

    concept = models.CharField(max_length=120)
    payment_type = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="Ej. Efectivo, Depósito, Infonavit",
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Siempre positivo; la categoría define si suma o resta.",
    )

    notes = models.CharField(max_length=280, blank=True, default="")

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["settlement", "category"]),
        ]

    def __str__(self) -> str:
        return f"{self.category} - {self.concept} (${self.amount})"

    def clean(self):
        super().clean()
        if self.amount is not None and self.amount < 0:
            raise ValidationError("El monto debe ser positivo. La categoría define si suma o resta.")
