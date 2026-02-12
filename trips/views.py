
# trips/views.py
import json
from datetime import datetime
from django import forms
from settlement.models import SettlementEvidence, REQUIRED_EVIDENCE_TYPES, EvidenceType
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_GET
from django.views.generic import (
    ListView, CreateView, UpdateView, DetailView, DeleteView, TemplateView
)

from locations.models import Route
from .models import Trip, TripStatus, CartaPorteCFDI
from .forms import (
    TripForm, TripSearchForm,
    CartaPorteCFDIForm,
    get_carta_porte_goods_formset,
)

from common.mixins import (
    OperacionRequiredMixin,
    OperadorRequiredMixin,
    OnlyMyTripsMixin,
    LockIfStampedMixin
)

FIELDS_AUDIT = [
    "route",
    "client",
    "operator",
    "transfer_operator",
    "truck",
    "reefer_box",
    "observations",
    "status",
    "arrival_origin_at",
    "departure_origin_at",
    "arrival_destination_at",
    "deleted",
]


# ============================================================
# OPERACIÓN (admin/superadmin/operacion)
# ============================================================

class TripListView(OperacionRequiredMixin, ListView):
    model = Trip
    template_name = "trips/list.html"
    context_object_name = "trips"
    paginate_by = 10

    def get_queryset(self):
        show_deleted = self.request.GET.get("show_deleted") == "1"
        show_all = self.request.GET.get("show_all") == "1"

        if show_all:
            qs = Trip.objects.all()
        elif show_deleted:
            qs = Trip.objects.filter(deleted=True)
        else:
            qs = Trip.objects.filter(deleted=False)

        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip().upper()
        transfer = (self.request.GET.get("transfer") or "").strip().lower()  # "1"/"0" o "si"/"no"

        if q:
            for token in q.split():
                qs = qs.filter(
                    Q(route__nombre__icontains=token) |
                    Q(route__origen__nombre__icontains=token) |
                    Q(route__destino__nombre__icontains=token) |
                    Q(client__nombre__icontains=token) |
                    Q(operator__nombre__icontains=token) |
                    Q(transfer_operator__nombre__icontains=token) |
                    Q(truck__numero_economico__icontains=token) |
                    Q(truck__placas__icontains=token) |
                    Q(reefer_box__numero_economico__icontains=token) |
                    Q(reefer_box__placas__icontains=token) |
                    Q(observations__icontains=token)
                )

        if status:
            qs = qs.filter(status=status)

        # transfer: si viene, filtra por si tiene o no operador de cruce
        if transfer in ("1", "si", "sí", "true", "yes"):
            qs = qs.filter(transfer_operator__isnull=False)
        elif transfer in ("0", "no", "false"):
            qs = qs.filter(transfer_operator__isnull=True)

        return (
            qs.select_related(
                "route", "route__origen", "route__destino",
                "client", "operator", "transfer_operator",
                "truck", "reefer_box"
            )
            .order_by("-id")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = TripSearchForm(self.request.GET or None)
        return ctx

    def get_paginate_by(self, queryset):
        try:
            return int(self.request.GET.get("page_size", self.paginate_by))
        except (TypeError, ValueError):
            return self.paginate_by


class TripCreateView(OperacionRequiredMixin, CreateView):
    model = Trip
    form_class = TripForm
    template_name = "trips/form.html"
    success_url = reverse_lazy("trips:list")

    def form_valid(self, form):
        # Guardar sin commit para snapshot
        self.object = form.save(commit=False)

        # Snapshot desde route
        self.object.apply_route_pricing_snapshot(force=False)

        self.object.save()
        form.save_m2m()

        messages.success(self.request, "Viaje creado correctamente.")
        return HttpResponseRedirect(self.get_success_url())


class TripUpdateView(LockIfStampedMixin, OperacionRequiredMixin, UpdateView):
    model = Trip
    form_class = TripForm
    template_name = "trips/form.html"
    success_url = reverse_lazy("trips:list")

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()

        if self.object.status != TripStatus.PROGRAMADO:
            messages.warning(
                request,
                "Este viaje no puede ser editado porque ya no está en estado Programado."
            )
            return redirect("trips:list")

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Viaje actualizado correctamente.")
        return super().form_valid(form)


class TripDetailView(OperacionRequiredMixin, DetailView):
    model = Trip
    template_name = "trips/detail.html"
    context_object_name = "trip"

    def get_queryset(self):
        return Trip.objects.all().select_related(
            "route", "route__origen", "route__destino",
            "client", "operator", "transfer_operator",
            "truck", "reefer_box"
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        trip = self.object

        carta = CartaPorteCFDI.objects.filter(trip=trip).only("id", "status", "uuid").first()

        ctx["carta"] = carta
        ctx["carta_is_stamped"] = bool(carta and carta.status == "stamped")
        ctx["carta_uuid"] = (carta.uuid if carta else "")
        return ctx


class TripSoftDeleteView(LockIfStampedMixin, OperacionRequiredMixin, DeleteView):
    model = Trip
    template_name = "trips/confirm_delete.html"
    success_url = reverse_lazy("trips:list")

    def get_queryset(self):
        return Trip.objects.filter(deleted=False)

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()

        if self.object.status != TripStatus.PROGRAMADO:
            messages.warning(
                request,
                "Este viaje no puede eliminarse porque ya no está en estado Programado."
            )
            return redirect("trips:list")

        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.deleted = True
        self.object.save(update_fields=["deleted"])
        messages.success(request, f"Viaje '{self.object}' eliminado correctamente.")
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


class TripBoardView(OperacionRequiredMixin, TemplateView):
    template_name = "trips/board.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()

        base_qs = Trip.objects.filter(deleted=False).exclude(status=TripStatus.CANCELADO)

        ctx["programados"] = base_qs.filter(status=TripStatus.PROGRAMADO)
        ctx["en_origen"] = base_qs.filter(status=TripStatus.EN_ORIGEN)
        ctx["en_curso"] = base_qs.filter(status=TripStatus.EN_CURSO)
        ctx["en_destino"] = base_qs.filter(status=TripStatus.EN_DESTINO)

        ctx["completados"] = Trip.objects.filter(
            deleted=False,
            status=TripStatus.COMPLETADO,
            arrival_destination_at__date=today,
        )

        ctx["today"] = today
        return ctx


class TripChangeStatusView(OperacionRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

        trip_id = data.get("trip_id")
        new_status = data.get("status")

        arrival_origin_at_str = data.get("arrival_origin_at")
        departure_origin_at_str = data.get("departure_origin_at")
        arrival_destination_at_str = data.get("arrival_destination_at")

        if not trip_id or not new_status:
            return JsonResponse({"ok": False, "error": "Datos incompletos"}, status=400)

        if new_status not in TripStatus.values:
            return JsonResponse({"ok": False, "error": "Estatus inválido"}, status=400)

        trip = get_object_or_404(Trip, pk=trip_id, deleted=False)

        def parse_dt(value: str):
            try:
                dt = datetime.fromisoformat(value)
            except Exception:
                return None
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            return dt

        if new_status == TripStatus.EN_ORIGEN:
            if not arrival_origin_at_str:
                return JsonResponse({"ok": False, "error": "Se requiere hora de llegada al origen"}, status=400)
            dt = parse_dt(arrival_origin_at_str)
            if not dt:
                return JsonResponse({"ok": False, "error": "Fecha/hora inválida"}, status=400)
            trip.status = TripStatus.EN_ORIGEN
            trip.arrival_origin_at = dt
            trip.save(update_fields=["status", "arrival_origin_at"])

        elif new_status == TripStatus.EN_CURSO:
            if not departure_origin_at_str:
                return JsonResponse({"ok": False, "error": "Se requiere hora de salida del origen"}, status=400)
            dt = parse_dt(departure_origin_at_str)
            if not dt:
                return JsonResponse({"ok": False, "error": "Fecha/hora inválida"}, status=400)
            trip.status = TripStatus.EN_CURSO
            trip.departure_origin_at = dt
            trip.save(update_fields=["status", "departure_origin_at"])

        elif new_status == TripStatus.EN_DESTINO:
            if not arrival_destination_at_str:
                return JsonResponse({"ok": False, "error": "Se requiere hora de llegada al destino"}, status=400)
            dt = parse_dt(arrival_destination_at_str)
            if not dt:
                return JsonResponse({"ok": False, "error": "Fecha/hora inválida"}, status=400)
            trip.status = TripStatus.EN_DESTINO
            trip.arrival_destination_at = dt
            trip.save(update_fields=["status", "arrival_destination_at"])

        else:
            trip.status = new_status
            trip.save(update_fields=["status"])

        return JsonResponse({
            "ok": True,
            "status": trip.status,
            "status_display": trip.get_status_display(),
            "updated_times": {
                "arrival_origin_at": trip.arrival_origin_at.strftime("%d/%m %H:%M") if trip.arrival_origin_at else None,
                "departure_origin_at": trip.departure_origin_at.strftime("%d/%m %H:%M") if trip.departure_origin_at else None,
                "arrival_destination_at": trip.arrival_destination_at.strftime("%d/%m %H:%M") if trip.arrival_destination_at else None,
            }
        })


@require_GET
def ajax_routes_by_client(request):
    # Proteger function-view igual que menú (operación)
    if not request.user.is_authenticated:
        return JsonResponse({"results": []}, status=401)
    if not request.user.groups.filter(name__in=["superadmin", "admin", "operacion"]).exists():
        return JsonResponse({"results": []}, status=403)

    client_id = request.GET.get("client_id")
    if not client_id:
        return JsonResponse({"results": []})

    routes = (
        Route.objects
        .filter(client_id=client_id, deleted=False)
        .select_related("origen", "destino")
        .order_by("origen__nombre", "destino__nombre")
    )

    results = [{"id": r.id, "label": f"{r.origen.nombre} → {r.destino.nombre}"} for r in routes]
    return JsonResponse({"results": results})


class CartaPorteCreateUpdateView(OperacionRequiredMixin, View):
    template_name = "trips/carta_porte_form.html"

    def get_trip_and_cp(self, trip_id):
        trip = get_object_or_404(Trip, pk=trip_id, deleted=False)
        carta_porte, _ = CartaPorteCFDI.objects.get_or_create(trip=trip)
        return trip, carta_porte

    def get(self, request, trip_id):
        trip, carta_porte = self.get_trip_and_cp(trip_id)

        GoodsFS = get_carta_porte_goods_formset()
        FiguresFS = get_carta_porte_transport_figure_formset()

        form = CartaPorteCFDIForm(instance=carta_porte)
        location_formset = LocationFS(instance=carta_porte)
        goods_formset = GoodsFS(instance=carta_porte)
        figures_formset = FiguresFS(instance=carta_porte)

        return render(request, self.template_name, {
            "trip": trip,
            "form": form,
            "location_formset": location_formset,
            "goods_formset": goods_formset,
            "figures_formset": figures_formset,
        })

    def post(self, request, trip_id):
        trip, carta_porte = self.get_trip_and_cp(trip_id)

        GoodsFS = get_carta_porte_goods_formset()
        FiguresFS = get_carta_porte_transport_figure_formset()

        form = CartaPorteCFDIForm(request.POST, instance=carta_porte)
        location_formset = LocationFS(request.POST, instance=carta_porte)
        goods_formset = GoodsFS(request.POST, instance=carta_porte)
        figures_formset = FiguresFS(request.POST, instance=carta_porte)

        if form.is_valid() and location_formset.is_valid() and goods_formset.is_valid() and figures_formset.is_valid():
            form.save()
            location_formset.save()
            goods_formset.save()
            figures_formset.save()
            return redirect("trips:detail", pk=trip.id)

        return render(request, self.template_name, {
            "trip": trip,
            "form": form,
            "location_formset": location_formset,
            "goods_formset": goods_formset,
            "figures_formset": figures_formset,
        })


# ============================================================
# OPERADOR (solo mis viajes)
# ============================================================

class MyTripListView(OperadorRequiredMixin, OnlyMyTripsMixin, ListView):
    model = Trip
    template_name = "trips/my_list.html"
    context_object_name = "trips"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().filter(deleted=False).select_related(
            "route", "route__origen", "route__destino",
            "truck", "reefer_box", "operator"
        )

        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip().upper()

        if q:
            for token in q.split():
                qs = qs.filter(
                    Q(route__nombre__icontains=token) |
                    Q(route__origen__nombre__icontains=token) |
                    Q(route__destino__nombre__icontains=token) |
                    Q(truck__numero_economico__icontains=token) |
                    Q(reefer_box__numero_economico__icontains=token) |
                    Q(observations__icontains=token)
                )

        if status:
            qs = qs.filter(status=status)

        return qs.order_by("-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = TripSearchForm(self.request.GET or None)
        return ctx


class MyTripDetailView(OperadorRequiredMixin, OnlyMyTripsMixin, DetailView):
    model = Trip
    template_name = "trips/my_detail.html"
    context_object_name = "trip"

    def get_queryset(self):
        return (
            super().get_queryset()
            .filter(deleted=False)
            .select_related(
                "route", "route__origen", "route__destino",
                "truck", "reefer_box", "operator"
            )
        )


class TripEvidenceView(View):
    """
    Evidencias para un Trip.
    Permite al operador o transfer_operator cargar:
        - Foto de carga
        - Foto de sello
    No permite subir si status == PROGRAMADO.
    """

    template_name = "trips/trip_evidence.html"

    # -----------------------------------------------------
    # Helpers
    # -----------------------------------------------------

    def get_operator(self):
        op = getattr(self.request.user, "operator_profile", None)
        if not op:
            raise Http404("Operador no encontrado.")
        return op

    def get_trip(self):
        trip = get_object_or_404(
            Trip.objects.select_related(
                "route", "route__origen", "route__destino",
                "client", "operator", "transfer_operator",
                "truck", "reefer_box",
            ),
            pk=self.kwargs["pk"],
            deleted=False,
        )

        op = self.get_operator()

        if trip.operator_id != op.id and trip.transfer_operator_id != op.id:
            raise Http404("No tienes acceso a este viaje.")

        return trip

    def build_context(self, trip):
        evidences = (
            SettlementEvidence.objects
            .filter(trip=trip, deleted=False)
            .order_by("-uploaded_at", "-id")
        )

        present = set(evidences.values_list("evidence_type", flat=True))
        missing_types = set(REQUIRED_EVIDENCE_TYPES) - present

        can_upload = (trip.status != TripStatus.PROGRAMADO)

        return {
            "trip": trip,
            "evidences": evidences,
            "EvidenceType": EvidenceType,
            "missing_types": missing_types,
            "can_upload": can_upload,
        }

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    def get(self, request, *args, **kwargs):
        trip = self.get_trip()
        return render(request, self.template_name, self.build_context(trip))

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    def post(self, request, *args, **kwargs):
        trip = self.get_trip()

        if trip.status == TripStatus.PROGRAMADO:
            messages.error(
                request,
                "No puedes subir evidencias mientras el viaje esté PROGRAMADO."
            )
            return redirect("trips:evidencia", pk=trip.pk)

        load_image = request.FILES.get("load_image")
        seal_image = request.FILES.get("seal_image")
        notes = request.POST.get("notes", "")

        if not load_image and not seal_image:
            messages.error(request, "Debes subir al menos una imagen.")
            return redirect("trips:evidencia", pk=trip.pk)

        # ---- CARGA ----
        if load_image:
            SettlementEvidence.objects.update_or_create(
                trip=trip,
                evidence_type=EvidenceType.LOAD,
                defaults={
                    "image": load_image,
                    "notes": notes,
                    "uploaded_by": request.user,
                    "uploaded_at": timezone.now(),
                    "deleted": False,
                }
            )

        # ---- SELLO ----
        if seal_image:
            SettlementEvidence.objects.update_or_create(
                trip=trip,
                evidence_type=EvidenceType.SEAL,
                defaults={
                    "image": seal_image,
                    "notes": notes,
                    "uploaded_by": request.user,
                    "uploaded_at": timezone.now(),
                    "deleted": False,
                }
            )

        messages.success(request, "Evidencias guardadas correctamente.")
        return redirect("trips:evidence", pk=trip.pk)
