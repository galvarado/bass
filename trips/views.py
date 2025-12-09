# trips/views.py
import json
from datetime import datetime
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect, JsonResponse
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView, TemplateView
from django.views import View
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render

from .models import Trip, TripStatus
from .forms import TripForm, TripSearchForm



# Ajusta esta lista según lo que quieras auditar en tu bitácora
FIELDS_AUDIT = [
    "origin",
    "destination",
    "operator",
    "truck",
    "reefer_box",
    "transfer",
    "observations",
    "status",
    "arrival_origin_at",
    "departure_origin_at",
    "arrival_destination_at",
    "deleted",
]


class TripListView(ListView):
    model = Trip
    template_name = "trips/list.html"
    context_object_name = "trips"
    paginate_by = 10

    def get_queryset(self):
        """
        - Por defecto muestra solo no eliminados (deleted=False).
        - Si ?show_deleted=1, muestra solo eliminados.
        - Si ?show_all=1, muestra todos (incluidos eliminados).
        - Filtro por status y transfer.
        - Búsqueda en origen, destino, operador, camión, caja y observaciones.
        """
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
        transfer = (self.request.GET.get("transfer") or "").strip().upper()

        if q:
            for token in q.split():
                qs = qs.filter(
                    Q(origin__nombre__icontains=token) |
                    Q(destination__nombre__icontains=token) |
                    Q(operator__nombre__icontains=token) |
                    Q(truck__economico__icontains=token) |
                    Q(truck__placas__icontains=token) |
                    Q(reefer_box__economico__icontains=token) |
                    Q(reefer_box__numero__icontains=token) |
                    Q(observations__icontains=token)
                )

        if status:
            qs = qs.filter(status=status)

        if transfer:
            qs = qs.filter(transfer=transfer)

        return qs.order_by("-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = TripSearchForm(self.request.GET or None)
        return ctx

    def get_paginate_by(self, queryset):
        try:
            return int(self.request.GET.get("page_size", self.paginate_by))
        except (TypeError, ValueError):
            return self.paginate_by


class TripCreateView(CreateView):
    model = Trip
    form_class = TripForm
    template_name = "trips/form.html"
    success_url = reverse_lazy("trips:list")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Viaje creado correctamente.")
        return resp


class TripUpdateView(UpdateView):
    model = Trip
    form_class = TripForm
    template_name = "trips/form.html"
    success_url = reverse_lazy("trips:list")

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()

        # Bloqueo: solo se puede editar si está en PROGRAMADO
        if self.object.status != "PROGRAMADO":
            messages.warning(
                request,
                "Este viaje no puede ser editado porque ya no está en estado Programado."
            )
            return redirect("trips:list")

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Viaje actualizado correctamente.")
        return super().form_valid(form)

class TripDetailView(DetailView):
    model = Trip
    template_name = "trips/detail.html"
    context_object_name = "trip"

    def get_queryset(self):
        # Permite ver detalle tanto vivos como eliminados
        return Trip.objects.all()


class TripSoftDeleteView(DeleteView):
    model = Trip
    template_name = "trips/confirm_delete.html"
    success_url = reverse_lazy("trips:list")

    def get_queryset(self):
        # Solo viajes no eliminados
        return Trip.objects.filter(deleted=False)

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()

        if self.object.status != "PROGRAMADO":
            messages.warning(
                request,
                "Este viaje no puede eliminarse porque ya no está en estado Programado."
            )
            return redirect("trips:list")

        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        """Soft delete: marcar deleted=True en lugar de borrar."""
        self.object = self.get_object()
        self.object.deleted = True
        self.object.save(update_fields=["deleted"])
        messages.success(request, f"Viaje '{self.object}' eliminado correctamente.")
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


    def delete(self, request, *args, **kwargs):
        """Soft delete en lugar de borrado físico."""
        self.object = self.get_object()
        self.object.delete()
        messages.success(request, f"Viaje '{self.object}' eliminado correctamente.")
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

class TripBoardView(TemplateView):
    template_name = "trips/board.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        today = timezone.localdate()

        # Base queryset: no eliminados y no cancelados
        base_qs = Trip.objects.filter(deleted=False).exclude(
            status=TripStatus.CANCELADO
        )

        ctx["programados"] = base_qs.filter(status=TripStatus.PROGRAMADO)
        ctx["en_origen"] = base_qs.filter(status=TripStatus.EN_ORIGEN)
        ctx["en_curso"] = base_qs.filter(status=TripStatus.EN_CURSO)
        ctx["en_destino"] = base_qs.filter(status=TripStatus.EN_DESTINO)

        # Completados SOLO los del día (ajusté a arrival_destination_at)
        ctx["completados"] = Trip.objects.filter(
            deleted=False,
            status=TripStatus.COMPLETADO,
            arrival_destination_at__date=today,
        )

        ctx["today"] = today
        return ctx

class TripChangeStatusView(View):
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

        # === Lógica por estatus ===

        if new_status == TripStatus.EN_ORIGEN:
            if not arrival_origin_at_str:
                return JsonResponse(
                    {"ok": False, "error": "Se requiere hora de llegada al origen"},
                    status=400,
                )
            dt = parse_dt(arrival_origin_at_str)
            if not dt:
                return JsonResponse(
                    {"ok": False, "error": "Fecha/hora inválida"}, status=400
                )
            trip.status = TripStatus.EN_ORIGEN
            trip.arrival_origin_at = dt
            trip.save(update_fields=["status", "arrival_origin_at"])

        elif new_status == TripStatus.EN_CURSO:
            if not departure_origin_at_str:
                return JsonResponse(
                    {"ok": False, "error": "Se requiere hora de salida del origen"},
                    status=400,
                )
            dt = parse_dt(departure_origin_at_str)
            if not dt:
                return JsonResponse(
                    {"ok": False, "error": "Fecha/hora inválida"}, status=400
                )
            trip.status = TripStatus.EN_CURSO
            trip.departure_origin_at = dt
            trip.save(update_fields=["status", "departure_origin_at"])

        elif new_status == TripStatus.EN_DESTINO:
            if not arrival_destination_at_str:
                return JsonResponse(
                    {"ok": False, "error": "Se requiere hora de llegada al destino"},
                    status=400,
                )
            dt = parse_dt(arrival_destination_at_str)
            if not dt:
                return JsonResponse(
                    {"ok": False, "error": "Fecha/hora inválida"}, status=400
                )
            trip.status = TripStatus.EN_DESTINO
            trip.arrival_destination_at = dt
            trip.save(update_fields=["status", "arrival_destination_at"])

        else:
            # PROGRAMADO, COMPLETADO, etc: solo cambiar status
            trip.status = new_status
            trip.save(update_fields=["status"])
            
        return JsonResponse({
            "ok": True,
            "status": trip.status,
            "status_display": trip.get_status_display(),
            "updated_times": {
                "arrival_origin_at":
                    trip.arrival_origin_at.strftime("%d/%m %H:%M") if trip.arrival_origin_at else None,
                "departure_origin_at":
                    trip.departure_origin_at.strftime("%d/%m %H:%M") if trip.departure_origin_at else None,
                "arrival_destination_at":
                    trip.arrival_destination_at.strftime("%d/%m %H:%M") if trip.arrival_destination_at else None,
            }
        })

from .models import Trip, CartaPorteCFDI
from .forms import (
    CartaPorteCFDIForm,
    CartaPorteLocationFormSet,
    CartaPorteGoodsFormSet,
    CartaPorteTransportFigureFormSet,
)


class CartaPorteCreateUpdateView(View):
    template_name = "trips/carta_porte_form.html"

    def get_trip_and_cp(self, pk):
        trip = get_object_or_404(Trip, pk=pk)
        carta_porte, created = CartaPorteCFDI.objects.get_or_create(trip=trip)
        return trip, carta_porte

    def get(self, request, trip_id):
        trip, carta_porte = self.get_trip_and_cp(trip_id)

        form = CartaPorteCFDIForm(instance=carta_porte)
        location_formset = CartaPorteLocationFormSet(instance=carta_porte)
        goods_formset = CartaPorteGoodsFormSet(instance=carta_porte)
        figures_formset = CartaPorteTransportFigureFormSet(instance=carta_porte)

        context = {
            "trip": trip,
            "form": form,
            "location_formset": location_formset,
            "goods_formset": goods_formset,
            "figures_formset": figures_formset,
        }
        return render(request, self.template_name, context)

    def post(self, request, trip_id):
        trip, carta_porte = self.get_trip_and_cp(trip_id)

        form = CartaPorteCFDIForm(request.POST, instance=carta_porte)
        location_formset = CartaPorteLocationFormSet(request.POST, instance=carta_porte)
        goods_formset = CartaPorteGoodsFormSet(request.POST, instance=carta_porte)
        figures_formset = CartaPorteTransportFigureFormSet(request.POST, instance=carta_porte)

        if (
            form.is_valid()
            and location_formset.is_valid()
            and goods_formset.is_valid()
            and figures_formset.is_valid()
        ):
            form.save()
            location_formset.save()
            goods_formset.save()
            figures_formset.save()
            # aquí podrías redirigir a detalle del viaje o a "previsualizar / timbrar"
            return redirect("trips:detail", pk=trip.id)

        context = {
            "trip": trip,
            "form": form,
            "location_formset": location_formset,
            "goods_formset": goods_formset,
            "figures_formset": figures_formset,
        }
        return render(request, self.template_name, context)