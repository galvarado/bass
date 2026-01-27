from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.db import transaction

from django.views.generic import (
    ListView, CreateView, UpdateView, DetailView, DeleteView
)
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

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
    context_object_name = "orders"  # histórico
    paginate_by = None  # manual para 3 paginadores

    def _paginate(self, qs, page_param, page_size_param, default_size=10):
        page = self.request.GET.get(page_param, 1)
        try:
            size = int(self.request.GET.get(page_size_param, default_size))
        except (TypeError, ValueError):
            size = default_size

        paginator = Paginator(qs, size)
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return paginator, page_obj, page_obj.object_list

    def get_queryset(self):
        # histórico se calcula en get_context_data (para no duplicar)
        return WorkshopOrder.objects.none()

    def _apply_filters_orders(self, qs, q, estado, tipo_unidad):
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

        return qs

    def _get_maintenance_requests(self, q, tipo_unidad):
        qs = MaintenanceRequest.objects.filter(deleted=False).select_related(
            "truck", "reefer_box", "orden_taller", "operador"
        ).filter(estado__in=["ABIERTA", "EVALUADA", "CONVERTIDA"])

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

        q = (self.request.GET.get("q") or "").strip()
        estado = (self.request.GET.get("estado") or "").strip()
        tipo_unidad = (self.request.GET.get("tipo_unidad") or "").strip()

        show_deleted = self.request.GET.get("show_deleted") == "1"
        show_all = self.request.GET.get("show_all") == "1"

        if show_all:
            base_orders = WorkshopOrder.objects.all()
        elif show_deleted:
            base_orders = WorkshopOrder.objects.filter(deleted=True)
        else:
            base_orders = WorkshopOrder.objects.filter(deleted=False)

        base_orders = self._apply_filters_orders(base_orders, q=q, estado=estado, tipo_unidad=tipo_unidad)

        # ===== Activas (paginadas) =====
        active_qs = base_orders.exclude(estado__in=["TERMINADA", "CANCELADA"]).order_by("-fecha_entrada")
        a_paginator, a_page_obj, a_list = self._paginate(
            active_qs, page_param="apage", page_size_param="apage_size", default_size=10
        )
        ctx["a_paginator"] = a_paginator
        ctx["a_page_obj"] = a_page_obj
        ctx["a_is_paginated"] = a_paginator.num_pages > 1
        ctx["active_orders"] = a_list
        ctx["apage"] = a_page_obj.number

        # ===== Históricas (paginadas) =====
        history_qs = base_orders.filter(estado__in=["TERMINADA", "CANCELADA"]).order_by("-fecha_entrada")
        paginator, page_obj, history_list = self._paginate(
            history_qs, page_param="page", page_size_param="page_size", default_size=10
        )
        ctx["paginator"] = paginator
        ctx["page_obj"] = page_obj
        ctx["is_paginated"] = paginator.num_pages > 1
        ctx["orders"] = history_list

        # ===== Maintenance Requests (paginadas) =====
        mr_qs = self._get_maintenance_requests(q=q, tipo_unidad=tipo_unidad)
        mr_paginator, mr_page_obj, mr_list = self._paginate(
            mr_qs, page_param="mrpage", page_size_param="mrpage_size", default_size=10
        )
        ctx["mr_paginator"] = mr_paginator
        ctx["mr_page_obj"] = mr_page_obj
        ctx["mr_is_paginated"] = mr_paginator.num_pages > 1
        ctx["maintenance_requests"] = mr_list

        # Search form
        ctx["search_form"] = WorkshopOrderSearchForm(self.request.GET or None)

        return ctx