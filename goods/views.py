
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView

from common.mixins import CatalogosRequiredMixin
from .models import Mercancia
from .forms import MercanciaForm, MercanciaSearchForm


# ============================================================
# Views (SOLO CATÁLOGOS / ADMIN / SUPERADMIN)
# ============================================================

class MercanciaListView(CatalogosRequiredMixin, ListView):
    model = Mercancia
    template_name = "goods/list.html"
    context_object_name = "mercancias"
    paginate_by = 10

    def get_queryset(self):
        show_deleted = self.request.GET.get("show_deleted") == "1"
        show_all = self.request.GET.get("show_all") == "1"

        # Solo admin/superadmin pueden ver eliminados
        is_gov = self.request.user.groups.filter(
            name__in=("superadmin", "admin")
        ).exists()

        if (show_deleted or show_all) and not is_gov:
            show_deleted = False
            show_all = False

        if show_all:
            qs = Mercancia.objects.all()
        elif show_deleted:
            qs = Mercancia.objects.filter(deleted=True)
        else:
            qs = Mercancia.alive.filter(deleted=False)

        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()

        if q:
            for token in q.split():
                qs = qs.filter(
                    Q(clave__icontains=token) |
                    Q(nombre__icontains=token) |
                    Q(fraccion_arancelaria__icontains=token) |
                    Q(comercio_exterior_uuid__icontains=token)
                )

        # status: ("1" activos, "0" eliminados) como tu patrón
        if status in ("1", "0"):
            if status == "1":
                qs = qs.filter(deleted=False)
            else:
                qs = Mercancia.objects.filter(pk__in=qs.values_list("pk", flat=True), deleted=True)

        return qs.order_by("clave", "nombre")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = MercanciaSearchForm(self.request.GET or None)
        return ctx

    def get_paginate_by(self, queryset):
        try:
            return int(self.request.GET.get("page_size", self.paginate_by))
        except (TypeError, ValueError):
            return self.paginate_by


class MercanciaCreateView(CatalogosRequiredMixin, CreateView):
    model = Mercancia
    form_class = MercanciaForm
    template_name = "goods/form.html"
    success_url = reverse_lazy("goods:list")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Mercancía creada correctamente.")
        return resp


class MercanciaUpdateView(CatalogosRequiredMixin, UpdateView):
    model = Mercancia
    form_class = MercanciaForm
    template_name = "goods/form.html"
    success_url = reverse_lazy("goods:list")

    def get_queryset(self):
        # editar incluso si está eliminada (solo Catálogos/Admin/Superadmin llegan aquí)
        return Mercancia.objects.all()

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Mercancía actualizada correctamente.")
        return resp


class MercanciaDetailView(CatalogosRequiredMixin, DetailView):
    model = Mercancia
    template_name = "goods/detail.html"
    context_object_name = "mercancia"

    def get_queryset(self):
        return Mercancia.objects.all()


class MercanciaSoftDeleteView(CatalogosRequiredMixin, DeleteView):
    model = Mercancia
    template_name = "goods/confirm_delete.html"
    success_url = reverse_lazy("goods:list")

    def get_queryset(self):
        return Mercancia.objects.all()

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete()

        messages.success(
            request,
            f"Mercancía '{self.object.clave} - {self.object.nombre}' eliminada correctamente."
        )
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

