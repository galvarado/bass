# locations/views.py
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView

from .models import Location
from .forms import LocationForm, LocationSearchForm


class LocationListView(ListView):
    model = Location
    template_name = "locations/list.html"
    context_object_name = "locations"
    paginate_by = 10

    def get_queryset(self):
        """
        - Por defecto muestra solo no eliminados (deleted=False).
        - Si ?show_deleted=1, muestra solo eliminados.
        - Si ?show_all=1, muestra todos (incluidos eliminados).
        - Filtro 'status' compatible con ("1"=Activas / deleted=False, "0"=Eliminadas / deleted=True).
        - Búsqueda: nombre de ubicación (y nombre de cliente para conveniencia).
        """
        show_deleted = self.request.GET.get("show_deleted") == "1"
        show_all = self.request.GET.get("show_all") == "1"

        if show_all:
            qs = Location.objects.all()
        elif show_deleted:
            qs = Location.objects.filter(deleted=True)
        else:
            qs = Location.objects.filter(deleted=False)

        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()

        if q:
            # Solo por nombre de ubicación; añadimos cliente como ayuda
            for token in q.split():
                qs = qs.filter(
                    Q(nombre__icontains=token) |
                    Q(client__nombre__icontains=token)
                )

        if status == "1":      # Activas
            qs = qs.filter(deleted=False)
        elif status == "0":    # Eliminadas
            qs = qs.filter(deleted=True)

        return qs.select_related("client").order_by("client__nombre", "nombre")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = LocationSearchForm(self.request.GET or None)
        return ctx

    def get_paginate_by(self, queryset):
        try:
            return int(self.request.GET.get("page_size", self.paginate_by))
        except (TypeError, ValueError):
            return self.paginate_by


class LocationCreateView(CreateView):
    model = Location
    form_class = LocationForm
    template_name = "locations/form.html"
    success_url = reverse_lazy("locations:list")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Ubicación creada correctamente.")
        return resp


class LocationUpdateView(UpdateView):
    model = Location
    form_class = LocationForm
    template_name = "locations/form.html"
    success_url = reverse_lazy("locations:list")

    def get_queryset(self):
        # Permite editar cualquier registro (incluyendo eliminados, si quieres bloquear, cambia a filter(deleted=False))
        return Location.objects.all()

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Ubicación actualizada correctamente.")
        return resp


class LocationDetailView(DetailView):
    model = Location
    template_name = "locations/detail.html"
    context_object_name = "location"

    def get_queryset(self):
        # Permite ver detalle tanto activas como eliminadas
        return Location.objects.all()


class LocationSoftDeleteView(DeleteView):
    model = Location
    template_name = "locations/confirm_delete.html"
    success_url = reverse_lazy("locations:list")

    def get_queryset(self):
        # Solo permite eliminar las que no están eliminadas
        return Location.objects.filter(deleted=False)

    def delete(self, request, *args, **kwargs):
        """Soft delete en lugar de borrado físico."""
        self.object = self.get_object()
        # Si tu modelo tiene método soft_delete(), podrías llamar self.object.soft_delete()
        self.object.deleted = True
        self.object.save(update_fields=["deleted"])
        messages.success(request, f"Ubicación «{self.object.nombre}» eliminada correctamente.")
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)
