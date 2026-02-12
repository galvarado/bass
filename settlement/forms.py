# settlement/forms.py
from __future__ import annotations

from django import forms
from django.db.models import Q

from trips.models import Trip, TripStatus
from .models import OperatorSettlement, OperatorSettlementLine, SettlementLineCategory, SettlementApprovalStatus


class OperatorSettlementForm(forms.ModelForm):
    """
    Encabezado + campos "operativos" del formato.
    NOTA: carga_en es display (readonly). baja_trip es selección.
    Los importes se guardan como líneas "ingreso" (conceptos fijos).
    """
    carga_en = forms.CharField(required=False, disabled=True)
    baja_trip = forms.ModelChoiceField(
        queryset=Trip.objects.none(),
        required=False,
        empty_label="— Sin baja —",
        widget=forms.Select(attrs={"class": "form-control form-control-sm"})
    )

    cruce_ida = forms.DecimalField(required=False, decimal_places=2, max_digits=10,
                                   widget=forms.NumberInput(attrs={"class":"form-control form-control-sm", "step":"0.01", "min":"0"}))
    cruce_vuelta = forms.DecimalField(required=False, decimal_places=2, max_digits=10,
                                      widget=forms.NumberInput(attrs={"class":"form-control form-control-sm", "step":"0.01", "min":"0"}))

    class Meta:
        model = OperatorSettlement
        fields = ["operator", "unit_label", "period_from", "period_to", "deposit_date", "notes"]
        widgets = {
            "operator": forms.Select(attrs={"class": "form-control form-control-sm"}),
            "unit_label": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "period_from": forms.DateInput(attrs={"class": "form-control form-control-sm", "type": "date"}),
            "period_to": forms.DateInput(attrs={"class": "form-control form-control-sm", "type": "date"}),
            "deposit_date": forms.DateInput(attrs={"class": "form-control form-control-sm", "type": "date"}),
            "notes": forms.Textarea(attrs={"class": "form-control form-control-sm", "rows": 2}),
        }

    def __init__(self, *args, load_trip: Trip | None = None, **kwargs):
        super().__init__(*args, **kwargs)

        # ✅ operador/unidad readonly
        self.fields["operator"].disabled = True
        self.fields["unit_label"].disabled = True

        # baja trips: mismo operador, COMPLETADO, aprobado, sin liquidación (si tienes flag), y no el mismo load
        if load_trip and load_trip.operator_id:
            qs = (
                Trip.objects
                .filter(
                    deleted=False,
                    operator_id=load_trip.operator_id,
                )
                .exclude(pk=load_trip.pk)
                .select_related("route", "route__origen", "route__destino")
            )

            # Reglas recomendadas (ajusta si tu flujo permite otros status):
            qs = qs.filter(status=TripStatus.COMPLETADO)

            # Debe estar aprobado evidencias:
            qs = qs.filter(
                Q(settlement_approval__status=SettlementApprovalStatus.APPROVED)
            )

            # Si tienes "has_settlement" ya anotado en list, aquí no. Si quieres bloquear:
            # qs = qs.exclude(settlement_memberships__isnull=False)  # ojo: si hay relación
            # Mejor:
            qs = qs.exclude(settlement_memberships__settlement__isnull=False)


            self.fields["baja_trip"].queryset = qs

            # carga_en (readonly)
            origen = getattr(load_trip.route, "origen", None)
            self.fields["carga_en"].initial = getattr(origen, "nombre", "") or str(origen or "—")


class OperatorSettlementLineForm(forms.ModelForm):
    class Meta:
        model = OperatorSettlementLine
        fields = ["category", "concept", "payment_type", "amount", "notes"]
        widgets = {
            "category": forms.HiddenInput(),
            "concept": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "payment_type": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "amount": forms.NumberInput(attrs={"class": "form-control form-control-sm", "step": "0.01", "min": "0"}),
            "notes": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
        }

    def clean_amount(self):
        v = self.cleaned_data.get("amount")
        if v is not None and v < 0:
            raise forms.ValidationError("El monto debe ser positivo.")
        return v


SettlementLineFormSet = forms.inlineformset_factory(
    OperatorSettlement,
    OperatorSettlementLine,
    form=OperatorSettlementLineForm,
    extra=0,
    can_delete=True,
)
