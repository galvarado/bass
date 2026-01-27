from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.db import transaction

from django.views.generic import (
    ListView, CreateView, UpdateView, DetailView, DeleteView
)

from .models import WorkshopOrder, MaintenanceRequest
from .forms import WorkshopOrderForm, WorkshopOrderSearchForm, SparePartUsageFormSet
from warehouse.models import SparePartMovement

from common.mixins import TallerRequiredMixin

# Campos que podrías auditar (ajusta según tu bitácora real)
FIELDS_AUDIT = [
    "truck",
    "reefer_box",
    "estado",
    "descripcion",
    "costo_mano_obra",
    "costo_refacciones",
    "otros_costos",
    "deleted",
]


class WorkshopOrderHistoryListView(TallerRequiredMixin, ListView):
    """
    (Opcional / legado) Lista histórica simple separando activas vs históricas.
    OJO: esta clase ya NO se llama WorkshopOrderListView para no pisar la principal.
    """
    model = WorkshopOrder
    template_name = "workshop/list.html"
    context_object_name = "orders"  # estas serán las históricas
    paginate_by = 10

    def get_queryset(self):
        show_deleted = self.request.GET.get("show_deleted") == "1"
        show_all = self.request.GET.get("show_all") == "1"

        if show_all:
            qs = WorkshopOrder.objects.all()
        elif show_deleted:
            qs = WorkshopOrder.objects.filter(deleted=True)
        else:
            qs = WorkshopOrder.objects.filter(deleted=False)

        q = (self.request.GET.get("q") or "").strip()
        estado = (self.request.GET.get("estado") or "").strip()
        tipo_unidad = (self.request.GET.get("tipo_unidad") or "").strip()

        if q:
            for token in q.split():
                qs = qs.filter(
                    Q(truck__numero_economico__icontains=token) |
                    Q(truck__placas__icontains=token) |
                    Q(reefer_box__numero_economico__icontains=token) |
                    Q(reefer_box__placas__icontains=token) |
                    Q(descripcion__icontains=token)
                )

        if estado:
            qs = qs.filter(estado=estado)

        if tipo_unidad == "TRUCK":
            qs = qs.filter(truck__isnull=False)
        elif tipo_unidad == "BOX":
            qs = qs.filter(reefer_box__isnull=False)

        activos = qs.exclude(estado__in=["TERMINADA", "CANCELADA"])
        historicos = qs.filter(estado__in=["TERMINADA", "CANCELADA"])

        self.active_orders = activos.order_by("-fecha_entrada")
        return historicos.order_by("-fecha_entrada")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = WorkshopOrderSearchForm(self.request.GET or None)
        ctx["active_orders"] = getattr(self, "active_orders", WorkshopOrder.objects.none())
        return ctx

    def get_paginate_by(self, queryset):
        try:
            return int(self.request.GET.get("page_size", self.paginate_by))
        except (TypeError, ValueError):
            return self.paginate_by


class WorkshopOrderCreateView(TallerRequiredMixin, CreateView):
    model = WorkshopOrder
    form_class = WorkshopOrderForm
    template_name = "workshop/form.html"
    success_url = reverse_lazy("workshop:list")

    def form_valid(self, form):
        # fuerza estado ABIERTA al crear
        ot = form.save(commit=False)
        ot.estado = "ABIERTA"
        ot.save()
        form.save_m2m()
        messages.success(self.request, "Orden de taller creada correctamente.")
        return HttpResponseRedirect(self.success_url)


class WorkshopOrderUpdateView(TallerRequiredMixin, UpdateView):
    model = WorkshopOrder
    form_class = WorkshopOrderForm
    template_name = "workshop/form.html"
    success_url = reverse_lazy("workshop:list")

    def get_queryset(self):
        # Solo órdenes no eliminadas
        return WorkshopOrder.objects.filter(deleted=False)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.method == "POST":
            ctx["formset"] = SparePartUsageFormSet(
                self.request.POST,
                instance=self.object,
            )
        else:
            ctx["formset"] = SparePartUsageFormSet(
                instance=self.object,
            )
        return ctx

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = SparePartUsageFormSet(self.request.POST, instance=self.object)

        if form.is_valid() and formset.is_valid():
            return self.form_valid_with_items(form, formset)
        else:
            return self.form_invalid(form)

    def form_valid_with_items(self, form, formset):
        """
        Guarda la OT + refacciones usadas.
        Convierte cantidad positiva en movimiento negativo (salida de inventario).
        """
        ot = form.save()

        instances = formset.save(commit=False)

        for obj in formset.deleted_objects:
            if isinstance(obj, SparePartMovement):
                obj.deleted = True
                obj.save(update_fields=["deleted"])

        for mv in instances:
            mv.movement_type = "WORKSHOP_USAGE"
            mv.workshop_order = ot

            if mv.quantity is None:
                continue

            if mv.quantity > 0:
                mv.quantity = -mv.quantity

            mv.save()

        messages.success(self.request, "Orden de taller actualizada correctamente.")
        return HttpResponseRedirect(self.success_url)


class WorkshopOrderDetailView(TallerRequiredMixin, DetailView):
    model = WorkshopOrder
    template_name = "workshop/detail.html"
    context_object_name = "ot"

    def get_queryset(self):
        return WorkshopOrder.objects.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ot = self.object

        movements = (
            ot.spare_part_movements
              .filter(movement_type="WORKSHOP_USAGE", deleted=False)
              .select_related("spare_part")
              .order_by("date", "id")
        )

        for mv in movements:
            mv.display_quantity = abs(mv.quantity or 0)

        ctx["spare_parts_used"] = movements
        return ctx


class WorkshopOrderSoftDeleteView(TallerRequiredMixin, DeleteView):
    model = WorkshopOrder
    template_name = "workshop/confirm_delete.html"
    success_url = reverse_lazy("workshop:list")

    def get_queryset(self):
        return WorkshopOrder.objects.filter(deleted=False)

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.estado in ("TERMINADA", "CANCELADA"):
            messages.error(
                request,
                "No puedes eliminar una orden de taller que está terminada o cancelada."
            )
            return HttpResponseRedirect(
                reverse_lazy("workshop:detail", kwargs={"pk": self.object.pk})
            )
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete()
        messages.success(
            request,
            f"Orden de taller 'OT {self.object.folio_interno}' eliminada correctamente."
        )
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


class WorkshopOrderListView(TallerRequiredMixin, ListView):
    model = WorkshopOrder
    template_name = "workshop/list.html"
    context_object_name = "orders"  # estas serán las históricas
    paginate_by = 10

    def get_queryset(self):
        """
        Órdenes de taller (OT):
        - Por defecto: solo no eliminadas (deleted=False).
        - Si ?show_deleted=1 → solo eliminadas.
        - Si ?show_all=1 → todas (incluidas eliminadas).
        - Filtros:
          * q: económico, placas, descripción.
          * estado: estado de OT.
          * tipo_unidad (virtual): TRUCK / BOX.
        - Separación:
          * active_orders (sin paginación)
          * orders (histórico con paginación)
        Además, en el contexto se agregan:
          * maintenance_requests (solicitudes de mantenimiento)
        """
        show_deleted = self.request.GET.get("show_deleted") == "1"
        show_all = self.request.GET.get("show_all") == "1"

        if show_all:
            qs = WorkshopOrder.objects.all()
        elif show_deleted:
            qs = WorkshopOrder.objects.filter(deleted=True)
        else:
            qs = WorkshopOrder.objects.filter(deleted=False)

        q = (self.request.GET.get("q") or "").strip()
        estado = (self.request.GET.get("estado") or "").strip()
        tipo_unidad = (self.request.GET.get("tipo_unidad") or "").strip()

        if q:
            for token in q.split():
                qs = qs.filter(
                    Q(truck__numero_economico__icontains=token) |
                    Q(truck__placas__icontains=token) |
                    Q(reefer_box__numero_economico__icontains=token) |
                    Q(reefer_box__placas__icontains=token) |
                    Q(descripcion__icontains=token)
                )

        if estado:
            qs = qs.filter(estado=estado)

        if tipo_unidad == "TRUCK":
            qs = qs.filter(truck__isnull=False)
        elif tipo_unidad == "BOX":
            qs = qs.filter(reefer_box__isnull=False)

        activos = qs.exclude(estado__in=["TERMINADA", "CANCELADA"])
        historicos = qs.filter(estado__in=["TERMINADA", "CANCELADA"])

        self.active_orders = activos.order_by("-fecha_entrada")

        self.maintenance_requests = self._get_maintenance_requests(q=q, tipo_unidad=tipo_unidad)

        return historicos.order_by("-fecha_entrada")

    def _get_maintenance_requests(self, q: str, tipo_unidad: str):
        qs = MaintenanceRequest.objects.filter(deleted=False).select_related(
            "truck", "reefer_box", "orden_taller", "operador"
        )

        qs = qs.filter(estado__in=["ABIERTA", "EVALUADA", "CONVERTIDA"])

        if q:
            for token in q.split():
                qs = qs.filter(
                    Q(truck__numero_economico__icontains=token) |
                    Q(truck__placas__icontains=token) |
                    Q(reefer_box__numero_economico__icontains=token) |
                    Q(reefer_box__placas__icontains=token) |
                    Q(descripcion__icontains=token)
                )

        if tipo_unidad == "TRUCK":
            qs = qs.filter(truck__isnull=False)
        elif tipo_unidad == "BOX":
            qs = qs.filter(reefer_box__isnull=False)

        return qs.order_by("-creado_en", "-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = WorkshopOrderSearchForm(self.request.GET or None)
        ctx["active_orders"] = getattr(self, "active_orders", WorkshopOrder.objects.none())
        ctx["maintenance_requests"] = getattr(
            self, "maintenance_requests", MaintenanceRequest.objects.none()
        )
        return ctx

    def get_paginate_by(self, queryset):
        try:
            return int(self.request.GET.get("page_size", self.paginate_by))
        except (TypeError, ValueError):
            return self.paginate_by
