# trips/views.py
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView

from .models import Trip
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

    def get_queryset(self):
        # Permite editar cualquier viaje (si quieres sólo vivos, usa Trip.alive.all())
        return Trip.objects.all()

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Viaje actualizado correctamente.")
        return resp


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
        # Solo permite eliminar no eliminados
        return Trip.objects.filter(deleted=False)

    def delete(self, request, *args, **kwargs):
        """Soft delete en lugar de borrado físico."""
        self.object = self.get_object()
        self.object.soft_delete()
        messages.success(request, f"Viaje '{self.object}' eliminado correctamente.")
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)
