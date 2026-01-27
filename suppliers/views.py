# suppliers/views.py
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView

from .models import Supplier
from .forms import SupplierForm, SupplierSearchForm
from common.mixins import CatalogosRequiredMixin

# (Opcional) lista para auditoría si luego metes bitácora
FIELDS_AUDIT = [
    "nombre", "razon_social",
    "contacto", "telefono", "email",
    "status", "cuenta",
    "calle", "no_ext", "colonia", "colonia_sat",
    "municipio", "estado", "pais", "cp", "poblacion",
    "deleted",
]


class SupplierListView(CatalogosRequiredMixin, ListView):
    model = Supplier
    template_name = "suppliers/list.html"
    context_object_name = "suppliers"
    paginate_by = 10

    def get_queryset(self):
        """
        - Por defecto muestra solo no eliminados (deleted=False).
        - Si ?show_deleted=1, muestra solo eliminados.
        - Si ?show_all=1, muestra todos (incluidos eliminados).
        - Soporta status 'ALTA'/'BAJA' y compat con '1'/'0' (1=ALTA, 0=BAJA).
        - Búsqueda por tokens en: nombre, razón social, contacto, teléfono, email, cuenta y dirección.
        """
        show_deleted = self.request.GET.get("show_deleted") == "1"
        show_all = self.request.GET.get("show_all") == "1"

        if show_all:
            qs = Supplier.objects.all()
        elif show_deleted:
            qs = Supplier.objects.filter(deleted=True)
        else:
            qs = Supplier.alive.filter(deleted=False)

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
                    Q(contacto__icontains=token) |
                    Q(telefono__icontains=token) |
                    Q(email__icontains=token) |
                    Q(cuenta__icontains=token) |
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
        ctx["search_form"] = SupplierSearchForm(self.request.GET or None)
        return ctx

    def get_paginate_by(self, queryset):
        try:
            return int(self.request.GET.get("page_size", self.paginate_by))
        except (TypeError, ValueError):
            return self.paginate_by


class SupplierCreateView(CatalogosRequiredMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = "suppliers/form.html"
    success_url = reverse_lazy("suppliers:list")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Proveedor creado correctamente.")
        return resp


class SupplierUpdateView(CatalogosRequiredMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = "suppliers/form.html"
    success_url = reverse_lazy("suppliers:list")

    def get_queryset(self):
        # Permitir editar cualquier registro (incluyendo eliminado)
        # Si quieres bloquear edición de eliminados: return Supplier.alive.filter(deleted=False)
        return Supplier.objects.all()

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Proveedor actualizado correctamente.")
        return resp


class SupplierDetailView(CatalogosRequiredMixin, DetailView):
    model = Supplier
    template_name = "suppliers/detail.html"
    context_object_name = "supplier"

    def get_queryset(self):
        # Permite ver detalle tanto vivos como eliminados
        return Supplier.objects.all()


class SupplierSoftDeleteView(CatalogosRequiredMixin, DeleteView):
    model = Supplier
    template_name = "suppliers/confirm_delete.html"
    success_url = reverse_lazy("suppliers:list")

    def get_queryset(self):
        # Solo permite eliminar no eliminados (si prefieres permitir re-eliminar, deja objects.all())
        return Supplier.objects.filter(deleted=False)

    def delete(self, request, *args, **kwargs):
        """Soft delete en lugar de borrado físico."""
        self.object = self.get_object()
        self.object.soft_delete()
        messages.success(request, f"Proveedor '{self.object}' eliminado correctamente.")
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)
