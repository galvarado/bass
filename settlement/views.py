# settlement/views.py
from __future__ import annotations

from django.contrib import messages
from django.db.models import (
    Q, Count, OuterRef, Subquery, Prefetch
)
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import (
    ListView, CreateView, UpdateView, DetailView
)

from common.mixins import OperacionRequiredMixin
from trips.models import Trip, TripStatus
from trips.forms import TripSearchForm

from .models import (
    OperatorSettlement,
    OperatorSettlementTrip,
    OperatorSettlementLine,
    SettlementTripRole,
    SettlementStatus,
    SettlementApprovalStatus,
    SettlementApproval,
    SettlementEvidence,
    REQUIRED_EVIDENCE_TYPES
)
from django.db.models import Q, Count, OuterRef, Subquery, Exists
import json
from django.http import JsonResponse
from django.views import View
from django.shortcuts import get_object_or_404
from django.db.models import Q

from django.http import HttpResponse
from django.template.loader import render_to_string

from .forms import OperatorSettlementForm, SettlementLineFormSet

from decimal import Decimal
from django.http import JsonResponse
from django.views import View

from .forms import OperatorSettlementForm, SettlementLineFormSet
from .models import SettlementLineCategory, SettlementTripRole, OperatorSettlementLine, OperatorSettlementTrip

# ============================================================
# LISTA: viajes COMPLETADOS para flujo de liquidación
# ============================================================
class CompletedTripsForSettlementListView(OperacionRequiredMixin, ListView):
    model = Trip
    template_name = "settlement/list.html"
    context_object_name = "trips"
    paginate_by = 10

    def get_queryset(self):
        # ✅ Subquery para saber si el trip ya está en alguna liquidación
        settlement_trip_exists = OperatorSettlementTrip.objects.filter(
            trip_id=OuterRef("pk")
        )

        qs = (
            Trip.objects
            .filter(deleted=False, status=TripStatus.COMPLETADO)
            .select_related(
                "route", "route__origen", "route__destino",
                "client",
                "operator",
                "transfer_operator",
                "truck",
                "reefer_box",
                "settlement_approval",
            )
            .annotate(
                evidence_count=Count(
                    "settlement_evidences",
                    filter=Q(settlement_evidences__deleted=False),
                ),
                # Para UI (si quieres mostrar el id, opcional)
                settlement_id=Subquery(
                    OperatorSettlementTrip.objects
                    .filter(trip_id=OuterRef("pk"))
                    .values("settlement_id")[:1]
                ),
                # ✅ bandera eficiente
                has_settlement=Exists(settlement_trip_exists),
            )
            # ✅ solo los que NO tienen liquidación
            .filter(has_settlement=False)
            .order_by("-arrival_destination_at", "-id")
        )

        q = (self.request.GET.get("q") or "").strip()
        transfer = (self.request.GET.get("transfer") or "").strip().lower()

        if q:
            for token in q.split():
                qs = qs.filter(
                    Q(route__nombre__icontains=token) |
                    Q(route__origen__nombre__icontains=token) |
                    Q(route__destino__nombre__icontains=token) |
                    Q(client__nombre__icontains=token) |
                    Q(operator__nombre__icontains=token) |
                    Q(truck__numero_economico__icontains=token) |
                    Q(truck__placas__icontains=token) |
                    Q(reefer_box__numero_economico__icontains=token) |
                    Q(observations__icontains=token)
                )

        if transfer in ("1", "si", "sí", "true", "yes"):
            qs = qs.filter(transfer_operator__isnull=False)
        elif transfer in ("0", "no", "false"):
            qs = qs.filter(transfer_operator__isnull=True)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = TripSearchForm(self.request.GET or None)
        return ctx


class SettlementListView(OperacionRequiredMixin, ListView):
    model = OperatorSettlement
    template_name = "settlement/settlement_list.html"
    context_object_name = "settlements"
    paginate_by = 10

    def get_queryset(self):
        qs = (
            OperatorSettlement.objects
            .select_related("operator", "created_by")
            .order_by("-created_at")
        )

        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip().lower()

        if q:
            for token in q.split():
                qs = qs.filter(
                    Q(operator__nombre__icontains=token) |
                    Q(unit_label__icontains=token) |
                    Q(notes__icontains=token)
                )

        if status:
            qs = qs.filter(status=status)

        return qs

        
class SettlementCreateView(OperacionRequiredMixin, CreateView):
    model = OperatorSettlement
    form_class = OperatorSettlementForm
    template_name = "settlement/form.html"

    def _get_load_trip(self) -> Trip | None:
        trip_load = (self.request.GET.get("trip_load") or "").strip()
        if not trip_load:
            return None
        return get_object_or_404(
            Trip.objects.select_related("operator", "truck", "route", "route__origen", "route__destino"),
            pk=int(trip_load), deleted=False
        )

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["load_trip"] = self._get_load_trip()
        return kw

    def get_initial(self):
        initial = super().get_initial()
        t = self._get_load_trip()
        if t:
            initial["operator"] = t.operator_id
            initial["unit_label"] = getattr(t.truck, "numero_economico", "") or ""
            # Opcional: periodo prefill con fechas del trip si tienes
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["trip_load"] = self._get_load_trip()
        if self.request.POST:
            ctx["line_formset"] = SettlementLineFormSet(self.request.POST)
        else:
            ctx["line_formset"] = SettlementLineFormSet()
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        line_formset = ctx["line_formset"]
        if not line_formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        self.object = form.save(commit=False)
        self.object.created_by = self.request.user
        self.object.status = SettlementStatus.DRAFT
        self.object.save()

        line_formset.instance = self.object
        line_formset.save()

        # Liga LOAD y (si viene) RETURN
        load_trip = self._get_load_trip()
        if load_trip:
            OperatorSettlementTrip.objects.update_or_create(
                settlement=self.object,
                role=SettlementTripRole.LOAD,
                defaults={"trip": load_trip},
            )

        baja_trip = form.cleaned_data.get("baja_trip")
        if baja_trip:
            OperatorSettlementTrip.objects.update_or_create(
                settlement=self.object,
                role=SettlementTripRole.RETURN,
                defaults={"trip": baja_trip},
            )

        # Sync líneas de ingresos (CARGA/BAJA/CRUCES) desde campos del form (JS las llena)
        self._sync_ingreso_lines_from_form(form)

        messages.success(self.request, "Liquidación creada correctamente.")
        return redirect("settlement:detail", pk=self.object.pk)

    def _sync_ingreso_lines_from_form(self, form):
        # Conceptos fijos para poder upsert
        CRUCE_IDA = "CRUCE IDA"
        CRUCE_VUELTA = "CRUCE VUELTA"
        PAGO_CARGA = "PAGO CARGA"
        PAGO_BAJA = "PAGO BAJA"

        # estos dos pagos los llenará el JS (y si no, quedan 0)
        pay_load = Decimal(str(self.request.POST.get("pay_load") or "0") or "0")
        pay_baja = Decimal(str(self.request.POST.get("pay_baja") or "0") or "0")

        cruce_ida = form.cleaned_data.get("cruce_ida") or Decimal("0")
        cruce_vuelta = form.cleaned_data.get("cruce_vuelta") or Decimal("0")

        def upsert(concept: str, amount: Decimal):
            OperatorSettlementLine.objects.update_or_create(
                settlement=self.object,
                category=SettlementLineCategory.INGRESO,
                concept=concept,
                defaults={"payment_type": "", "amount": amount, "notes": ""},
            )

        upsert(PAGO_CARGA, pay_load)
        # Solo crea PAGO BAJA si hay baja_trip
        if form.cleaned_data.get("baja_trip"):
            upsert(PAGO_BAJA, pay_baja)
        else:
            OperatorSettlementLine.objects.filter(
                settlement=self.object, category=SettlementLineCategory.INGRESO, concept=PAGO_BAJA
            ).delete()

        upsert(CRUCE_IDA, cruce_ida)
        upsert(CRUCE_VUELTA, cruce_vuelta)


class SettlementUpdateView(OperacionRequiredMixin, UpdateView):
    model = OperatorSettlement
    form_class = OperatorSettlementForm
    template_name = "settlement/form.html"

    def _get_load_trip(self) -> Trip | None:
        s = self.get_object()
        rel = s.trips.filter(role=SettlementTripRole.LOAD).select_related("trip", "trip__route", "trip__route__origen").first()
        return rel.trip if rel else None

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["load_trip"] = self._get_load_trip()
        return kw

    def get_initial(self):
        initial = super().get_initial()

        # precargar baja_trip si existe
        s = self.get_object()
        rel = s.trips.filter(role=SettlementTripRole.RETURN).select_related("trip").first()
        if rel:
            initial["baja_trip"] = rel.trip_id

        # precargar cruce ida/vuelta desde líneas ingreso
        def get_ing(concept):
            l = s.lines.filter(category=SettlementLineCategory.INGRESO, concept=concept).first()
            return l.amount if l else None

        initial["cruce_ida"] = get_ing("CRUCE IDA") or 0
        initial["cruce_vuelta"] = get_ing("CRUCE VUELTA") or 0
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["trip_load"] = self._get_load_trip()
        if self.request.POST:
            ctx["line_formset"] = SettlementLineFormSet(self.request.POST, instance=self.object)
        else:
            ctx["line_formset"] = SettlementLineFormSet(instance=self.object)
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        line_formset = ctx["line_formset"]
        if not line_formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        self.object = form.save()
        line_formset.instance = self.object
        line_formset.save()

        # update baja_trip relación
        baja_trip = form.cleaned_data.get("baja_trip")
        if baja_trip:
            OperatorSettlementTrip.objects.update_or_create(
                settlement=self.object,
                role=SettlementTripRole.RETURN,
                defaults={"trip": baja_trip},
            )
        else:
            OperatorSettlementTrip.objects.filter(
                settlement=self.object, role=SettlementTripRole.RETURN
            ).delete()

        # sync ingresos desde form
        self._sync_ingreso_lines_from_form(form)

        messages.success(self.request, "Liquidación actualizada.")
        return redirect("settlement:detail", pk=self.object.pk)

    def _sync_ingreso_lines_from_form(self, form):
        # mismo helper que arriba
        CRUCE_IDA = "CRUCE IDA"
        CRUCE_VUELTA = "CRUCE VUELTA"
        PAGO_CARGA = "PAGO CARGA"
        PAGO_BAJA = "PAGO BAJA"

        pay_load = Decimal(str(self.request.POST.get("pay_load") or "0") or "0")
        pay_baja = Decimal(str(self.request.POST.get("pay_baja") or "0") or "0")

        cruce_ida = form.cleaned_data.get("cruce_ida") or Decimal("0")
        cruce_vuelta = form.cleaned_data.get("cruce_vuelta") or Decimal("0")

        def upsert(concept: str, amount: Decimal):
            OperatorSettlementLine.objects.update_or_create(
                settlement=self.object,
                category=SettlementLineCategory.INGRESO,
                concept=concept,
                defaults={"payment_type": "", "amount": amount, "notes": ""},
            )

        upsert(PAGO_CARGA, pay_load)
        if form.cleaned_data.get("baja_trip"):
            upsert(PAGO_BAJA, pay_baja)
        else:
            OperatorSettlementLine.objects.filter(
                settlement=self.object, category=SettlementLineCategory.INGRESO, concept=PAGO_BAJA
            ).delete()

        upsert(CRUCE_IDA, cruce_ida)
        upsert(CRUCE_VUELTA, cruce_vuelta)

# ============================================================
# SETTLEMENT: DETAIL
# ============================================================

class SettlementDetailView(OperacionRequiredMixin, DetailView):
    model = OperatorSettlement
    template_name = "settlement/detail.html"
    context_object_name = "settlement"

    def get_queryset(self):
        settlement_trips_qs = (
            OperatorSettlementTrip.objects
            .select_related(
                "trip",
                "trip__route", "trip__route__origen", "trip__route__destino",
                "trip__client",
                "trip__operator",
                "trip__truck",
                "trip__reefer_box",
                "trip__settlement_approval",
            )
        )

        return (
            OperatorSettlement.objects
            .select_related("operator", "created_by")
            .prefetch_related(
                Prefetch("trips", queryset=settlement_trips_qs),
                "lines",
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        s: OperatorSettlement = self.object

        load_rel = next((r for r in s.trips.all() if r.role == SettlementTripRole.LOAD), None)
        return_rel = next((r for r in s.trips.all() if r.role == SettlementTripRole.RETURN), None)

        ctx["load_trip"] = load_rel.trip if load_rel else None
        ctx["return_trip"] = return_rel.trip if return_rel else None

        lines = list(s.lines.all())
        ctx["lines_ingreso"] = [l for l in lines if l.category == "ingreso"]
        ctx["lines_anticipo"] = [l for l in lines if l.category == "anticipo"]
        ctx["lines_gasto"] = [l for l in lines if l.category == "gasto"]
        ctx["lines_caseta"] = [l for l in lines if l.category == "caseta"]

        ctx["is_ready"] = (s.status == SettlementStatus.READY)
        ctx["is_paid"] = (s.status == SettlementStatus.PAID)

        return ctx


# ============================================================
# SETTLEMENT: ASIGNAR VIAJES (LOAD / RETURN)
# ============================================================

class SettlementAssignTripsView(OperacionRequiredMixin, UpdateView):
    model = OperatorSettlement
    fields = []
    template_name = "settlement/assign_trips.html"

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        trip_load_id = request.POST.get("trip_load_id")
        trip_return_id = (request.POST.get("trip_return_id") or "").strip() or None

        if not trip_load_id:
            messages.error(request, "Debes seleccionar el viaje de CARGA.")
            return redirect("settlement:detail", pk=self.object.pk)

        load_trip = get_object_or_404(Trip, pk=trip_load_id, deleted=False)
        if load_trip.status == TripStatus.PROGRAMADO:
            messages.error(request, "El viaje de CARGA no puede estar PROGRAMADO.")
            return redirect("settlement:detail", pk=self.object.pk)

        appr = getattr(load_trip, "settlement_approval", None)
        if not appr or appr.status != SettlementApprovalStatus.APPROVED:
            messages.error(request, "El viaje de CARGA no está aprobado.")
            return redirect("settlement:detail", pk=self.object.pk)

        OperatorSettlementTrip.objects.update_or_create(
            settlement=self.object,
            role=SettlementTripRole.LOAD,
            defaults={"trip": load_trip},
        )

        if trip_return_id:
            return_trip = get_object_or_404(Trip, pk=trip_return_id, deleted=False)
            if return_trip.status == TripStatus.PROGRAMADO:
                messages.error(request, "El viaje de BAJA no puede estar PROGRAMADO.")
                return redirect("settlement:detail", pk=self.object.pk)

            appr2 = getattr(return_trip, "settlement_approval", None)
            if not appr2 or appr2.status != SettlementApprovalStatus.APPROVED:
                messages.error(request, "El viaje de BAJA no está aprobado.")
                return redirect("settlement:detail", pk=self.object.pk)

            OperatorSettlementTrip.objects.update_or_create(
                settlement=self.object,
                role=SettlementTripRole.RETURN,
                defaults={"trip": return_trip},
            )
        else:
            OperatorSettlementTrip.objects.filter(
                settlement=self.object,
                role=SettlementTripRole.RETURN,
            ).delete()

        messages.success(request, "Viajes asignados correctamente.")
        return redirect("settlement:detail", pk=self.object.pk)


# ============================================================
# SETTLEMENT: MARCAR LISTA
# ============================================================

class SettlementMarkReadyView(OperacionRequiredMixin, UpdateView):
    model = OperatorSettlement
    fields = []
    template_name = "settlement/confirm_ready.html"

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        try:
            self.object.validate_trips_ready_for_settlement()
        except Exception as e:
            messages.error(request, str(e))
            return redirect("settlement:detail", pk=self.object.pk)

        self.object.status = SettlementStatus.READY
        self.object.save(update_fields=["status"])

        messages.success(request, "Liquidación marcada como LISTA.")
        return redirect("settlement:detail", pk=self.object.pk)



class AjaxTripEvidencesView(OperacionRequiredMixin, View):
    def get(self, request, trip_id):
        trip = get_object_or_404(
            Trip.objects.select_related("route", "operator", "client"),
            pk=trip_id,
            deleted=False
        )

        evidences = (
            SettlementEvidence.objects
            .filter(trip=trip, deleted=False)
            .order_by("-uploaded_at", "-id")
        )

        present = set(evidences.values_list("evidence_type", flat=True))
        missing_types = list(set(REQUIRED_EVIDENCE_TYPES) - present)

        appr = getattr(trip, "settlement_approval", None)
        approval_status = (appr.status if appr else "draft")

        data = {
            "trip_id": trip.id,
            "trip_label": f"#{trip.id} · {trip.route} · {trip.client}",
            "approval_status": approval_status,
            "missing_types": missing_types,
            "evidences": [
                {
                    "id": e.id,
                    "evidence_type": e.evidence_type,
                    "type_label": e.get_evidence_type_display(),
                    "notes": e.notes,
                    "uploaded_at": e.uploaded_at.strftime("%d/%m/%Y %H:%M") if e.uploaded_at else None,
                    "url": e.image.url if e.image else "",
                }
                for e in evidences
            ],
        }
        return JsonResponse(data)


class AjaxTripApprovalDecisionView(OperacionRequiredMixin, View):
    def post(self, request, trip_id):
        trip = get_object_or_404(Trip, pk=trip_id, deleted=False)

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

        action = (payload.get("action") or "").strip().lower()
        notes = (payload.get("notes") or "").strip()

        appr, _ = SettlementApproval.objects.get_or_create(trip=trip)

        if action == "approve":
            try:
                appr.approve(request.user, notes=notes)
            except Exception as e:
                return JsonResponse({"ok": False, "error": str(e)}, status=400)
            return JsonResponse({"ok": True})

        if action == "reject":
            appr.reject(request.user, notes=notes)
            return JsonResponse({"ok": True})

        return JsonResponse({"ok": False, "error": "Acción no soportada"}, status=400)

def get_operator_pay_for_trip(trip: Trip | None) -> Decimal:
    if not trip:
        return Decimal("0.00")
    return trip.pago_operador_snapshot or Decimal("0.00")

class AjaxTripPricingForSettlementView(OperacionRequiredMixin, View):
    def get(self, request, trip_load_id, trip_baja_id):
        load_trip = get_object_or_404(
            Trip.objects.select_related("route", "route__origen", "route__destino", "operator"),
            pk=trip_load_id, deleted=False
        )

        baja_trip = None
        if int(trip_baja_id) != 0:
            baja_trip = get_object_or_404(
                Trip.objects.select_related("route", "route__origen", "route__destino", "operator"),
                pk=trip_baja_id, deleted=False
            )

            # seguridad: mismo operador
            if baja_trip.operator_id != load_trip.operator_id:
                return JsonResponse({"ok": False, "error": "El viaje de BAJA debe ser del mismo operador."}, status=400)

        carga_en = getattr(getattr(load_trip.route, "origen", None), "nombre", "") or "—"
        baja_en = getattr(getattr(baja_trip.route, "destino", None), "nombre", "") if baja_trip else "—"

        pay_load = get_operator_pay_for_trip(load_trip)
        pay_baja = get_operator_pay_for_trip(baja_trip)

        return JsonResponse({
            "ok": True,
            "carga_en": carga_en,
            "baja_en": baja_en,
            "pay_load": str(pay_load),
            "pay_baja": str(pay_baja),
        })
    """
    Devuelve labels + montos sugeridos para:
    - CARGA EN (origen)
    - BAJA EN (destino)
    - Pago ruta carga (ingreso)
    - Pago ruta baja (ingreso) (si hay baja)
    """
    def get(self, request, trip_load_id, trip_baja_id):
        load_trip = get_object_or_404(
            Trip.objects.select_related("route", "route__origen", "route__destino", "operator"),
            pk=trip_load_id, deleted=False
        )

        baja_trip = None
        if int(trip_baja_id) != 0:
            baja_trip = get_object_or_404(
                Trip.objects.select_related("route", "route__origen", "route__destino", "operator"),
                pk=trip_baja_id, deleted=False
            )

        carga_en = getattr(getattr(load_trip.route, "origen", None), "nombre", "") or "—"
        baja_en = getattr(getattr(baja_trip.route, "destino", None), "nombre", "") if baja_trip else "—"

        pay_load = get_operator_pay_for_trip(load_trip)
        pay_baja = get_operator_pay_for_trip(baja_trip) if baja_trip else Decimal("0.00")

        return JsonResponse({
            "ok": True,
            "carga_en": carga_en,
            "baja_en": baja_en,
            "pay_load": str(pay_load),
            "pay_baja": str(pay_baja),
        })