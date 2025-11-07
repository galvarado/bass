# trucks/views.py (extracto relevante)
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView

from .models import Truck, ReeferBox
from .forms import TruckForm, TruckSearchForm, ReeferBoxForm


class TruckReeferCombinedListView(ListView):
    """
    Lista combinada de Camiones y Cajas en la misma página.
    - Usa template 'trucks/list.html'
    - Busca por 'q' en ambos modelos (incluye 'nombre')
    - Paginación independiente: tpage / bpage (y tamaños tpage_size / bpage_size)
    - Flags show_all / show_deleted aplican a ambos (si los envías)
    """
    model = Truck
    template_name = "trucks/list.html"
    context_object_name = "trucks"   # en el template seguimos usando 'trucks' y 'boxes'
    paginate_by = None               # manejamos paginación manual por cada queryset

    # ---------- Helpers ----------
    def _filter_trucks(self, base_qs):
        q = (self.request.GET.get("q") or "").strip()
        if q:
            for token in q.split():
                base_qs = base_qs.filter(
                    Q(nombre__icontains=token) |
                    Q(numero_economico__icontains=token) |
                    Q(placas__icontains=token) |
                    Q(serie__icontains=token) |
                    Q(marca__icontains=token) |
                    Q(motor__icontains=token) |
                    Q(categoria__icontains=token) |
                    Q(combustible__icontains=token) |
                    Q(rin__icontains=token)
                )
        return base_qs.order_by("numero_economico")

    def _filter_boxes(self, base_qs):
        q = (self.request.GET.get("q") or "").strip()
        if q:
            for token in q.split():
                base_qs = base_qs.filter(
                    Q(nombre__icontains=token) |
                    Q(numero_economico__icontains=token) |
                    Q(placas__icontains=token) |
                    Q(numero_serie__icontains=token) |
                    Q(marca__icontains=token) |
                    Q(modelo__icontains=token) |
                    Q(tipo_remolque__icontains=token) |
                    Q(categoria__icontains=token)
                )
        return base_qs.order_by("numero_economico")

    def _apply_deleted_flags(self, Model):
        show_deleted = self.request.GET.get("show_deleted") == "1"
        show_all = self.request.GET.get("show_all") == "1"

        if hasattr(Model, "all_objects"):
            if show_all:
                return Model.all_objects.all()
            elif show_deleted:
                return Model.all_objects.filter(deleted=True)
            else:
                return Model.objects.all()
        # fallback por si no hubiera managers especiales
        if show_all:
            return Model.objects.all()
        elif show_deleted:
            return Model.objects.filter(deleted=True)
        else:
            return Model.objects.filter(deleted=False)

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

    # ---------- Queryset principal (camiones) ----------
    def get_queryset(self):
        trucks_qs = self._apply_deleted_flags(Truck)
        trucks_qs = self._filter_trucks(trucks_qs)
        # Guardamos para usarlo en get_context_data (evitamos recalcular)
        self._trucks_qs = trucks_qs
        return trucks_qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Paginación y conteos CAMIONES
        t_paginator, t_page_obj, t_list = self._paginate(self._trucks_qs, page_param="tpage", page_size_param="tpage_size")
        ctx["paginator"] = t_paginator
        ctx["page_obj"] = t_page_obj
        ctx["trucks"] = t_list

        # BOXES: flags, filtro, paginación
        boxes_qs = self._apply_deleted_flags(ReeferBox)
        boxes_qs = self._filter_boxes(boxes_qs)
        b_paginator, b_page_obj, b_list = self._paginate(boxes_qs, page_param="bpage", page_size_param="bpage_size")
        ctx["b_paginator"] = b_paginator
        ctx["b_page_obj"] = b_page_obj
        ctx["boxes"] = b_list

        # Form de búsqueda (puedes usar TruckSearchForm como barra única)
        ctx["search_form"] = TruckSearchForm(self.request.GET or None)

        # KPIs de totales visibles en la tabla actual (no los totales de la BD)
        ctx["trucks_count"] = t_paginator.count
        ctx["boxes_count"] = b_paginator.count
        return ctx


# ====== El resto de vistas CRUD puede permanecer igual ======

class TruckCreateView(CreateView):
    model = Truck
    form_class = TruckForm
    template_name = "trucks/trucks_form.html"
    success_url = reverse_lazy("trucks:list")  # vuelve a la lista combinada

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Camión creado correctamente.")
        return resp


class TruckUpdateView(UpdateView):
    model = Truck
    form_class = TruckForm
    template_name = "trucks/form.html"
    success_url = reverse_lazy("trucks:list")

    def get_queryset(self):
        return Truck.objects.all()

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Camión actualizado correctamente.")
        return resp


class TruckDetailView(DetailView):
    model = Truck
    template_name = "trucks/detail.html"
    context_object_name = "truck"

    def get_queryset(self):
        return Truck.all_objects.all()


class TruckSoftDeleteView(DeleteView):
    model = Truck
    template_name = "trucks/confirm_delete.html"
    success_url = reverse_lazy("trucks:list")

    def get_queryset(self):
        return Truck.objects.all()

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete()
        messages.success(request, f"Camión '{self.object.numero_economico}' eliminado correctamente.")
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


class ReeferBoxCreateView(CreateView):
    model = ReeferBox
    form_class = ReeferBoxForm
    template_name = "trucks/reeferbox_form.html"
    success_url = reverse_lazy("trucks:list")  # vuelve a la lista combinada

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Caja refrigerada creada correctamente.")
        return resp


class ReeferBoxUpdateView(UpdateView):
    model = ReeferBox
    form_class = ReeferBoxForm
    template_name = "reeferboxes/form.html"
    success_url = reverse_lazy("trucks:list")

    def get_queryset(self):
        return ReeferBox.objects.all()

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Caja refrigerada actualizada correctamente.")
        return resp


class ReeferBoxDetailView(DetailView):
    model = ReeferBox
    template_name = "reeferboxes/detail.html"
    context_object_name = "box"

    def get_queryset(self):
        return ReeferBox.all_objects.all()


class ReeferBoxSoftDeleteView(DeleteView):
    model = ReeferBox
    template_name = "reeferboxes/confirm_delete.html"
    success_url = reverse_lazy("trucks:list")

    def get_queryset(self):
        return ReeferBox.objects.all()

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete()
        messages.success(request, f"Caja refrigerada '{self.object.numero_economico}' eliminada correctamente.")
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)
