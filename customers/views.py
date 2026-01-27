# customers/views.py
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView

from .models import Client
from .forms import ClientForm, ClientSearchForm
from common.mixins import CatalogosRequiredMixin

# Ajusta esta lista según lo que audites en tu bitácora
FIELDS_AUDIT = [
    "nombre", "razon_social", "rfc", "regimen_fiscal", "id_tributario",
    "telefono", "status", "deleted",
    "limite_credito", "dias_credito", "forma_pago", "cuenta", "uso_cfdi",
]


class ClientListView(CatalogosRequiredMixin, ListView):
    model = Client
    template_name = "customers/list.html"
    context_object_name = "clients"
    paginate_by = 10

    def get_queryset(self):
        """
        - Por defecto muestra solo no eliminados (deleted=False).
        - Si ?show_deleted=1, muestra solo eliminados.
        - Si ?show_all=1, muestra todos (incluidos eliminados).
        - Soporta status 'ALTA'/'BAJA' y compat con '1'/'0' (1=ALTA, 0=BAJA).
        - Búsqueda en nombre, razón social, RFC, cuenta, teléfono y dirección.
        """
        show_deleted = self.request.GET.get("show_deleted") == "1"
        show_all = self.request.GET.get("show_all") == "1"

        if show_all:
            qs = Client.objects.all()
        elif show_deleted:
            qs = Client.objects.filter(deleted=True)
        else:
            qs = Client.alive.filter(deleted=False)

        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip().upper()

        # Compatibilidad '1'/'0'
        if status in ("1", "0"):
            status = "ALTA" if status == "1" else "BAJA"

        if q:
            for token in q.split():
                qs = qs.filter(
                    Q(nombre__icontains=token) |
                    Q(razon_social__icontains=token) |
                    Q(rfc__icontains=token) |
                    Q(cuenta__icontains=token) |
                    Q(telefono__icontains=token) |
                    Q(calle__icontains=token) |
                    Q(colonia__icontains=token) |
                    Q(municipio__icontains=token) |
                    Q(estado__icontains=token) |
                    Q(cp__icontains=token)
                )

        if status in ("ALTA", "BAJA"):
            qs = qs.filter(status=status)

        return qs.order_by("nombre")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = ClientSearchForm(self.request.GET or None)
        return ctx

    def get_paginate_by(self, queryset):
        try:
            return int(self.request.GET.get("page_size", self.paginate_by))
        except (TypeError, ValueError):
            return self.paginate_by


class ClientCreateView(CatalogosRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = "customers/form.html"
    success_url = reverse_lazy("customers:list")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Cliente creado correctamente.")
        return resp


class ClientUpdateView(CatalogosRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = "customers/form.html"
    success_url = reverse_lazy("customers:list")

    def get_queryset(self):
        # Permitir editar cualquier registro (incluyendo eliminado si deseas bloquear, cámbialo a .alive)
        return Client.objects.all()

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Cliente actualizado correctamente.")
        return resp


class ClientDetailView(CatalogosRequiredMixin, DetailView):
    model = Client
    template_name = "customers/detail.html"
    context_object_name = "client"

    def get_queryset(self):
        # Permite ver detalle tanto vivos como eliminados
        return Client.objects.all()


class ClientSoftDeleteView(CatalogosRequiredMixin, DeleteView):
    model = Client
    template_name = "customers/confirm_delete.html"
    success_url = reverse_lazy("customers:list")

    def get_queryset(self):
        # Solo permite eliminar no eliminados (si prefieres permitir re-eliminar, deja objects.all())
        return Client.objects.filter(deleted=False)

    def delete(self, request, *args, **kwargs):
        """Soft delete en lugar de borrado físico."""
        self.object = self.get_object()
        self.object.soft_delete()
        messages.success(request, f"Cliente '{self.object}' eliminado correctamente.")
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)
