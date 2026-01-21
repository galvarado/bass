# trucks/views.py
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
    - Expone:
        CAMIONES: paginator, page_obj, is_paginated, trucks
        CAJAS:    b_paginator, b_page_obj, b_is_paginated, boxes
        Extras:   tab, search_form, trucks_count, boxes_count
    """
    model = Truck
    template_name = "trucks/list.html"
    context_object_name = "trucks"
    paginate_by = None  # paginación manual por queryset

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

        # Si el modelo tiene all_objects, úsalo para poder ver todo (incluidos borrados)
        if hasattr(Model, "all_objects"):
            base_qs = Model.all_objects.all()
        else:
            base_qs = Model.objects.all()

        if show_all:
            return base_qs
        elif show_deleted:
            return base_qs.filter(deleted=True)
        else:
            return base_qs.filter(deleted=False)

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

        # Guardamos para reutilizar sin recalcular
        self._trucks_qs = trucks_qs
        return trucks_qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Tab activo (para que el template pueda marcar el tab correcto)
        ctx["tab"] = self.request.GET.get("tab") or "trucks"

        # ---------------- CAMIONES ----------------
        t_paginator, t_page_obj, t_list = self._paginate(
            self._trucks_qs,
            page_param="tpage",
            page_size_param="tpage_size",
            default_size=10,
        )

        # Alias “estándar” estilo ListView para que tu template copie-pega el de Operadores
        ctx["paginator"] = t_paginator
        ctx["page_obj"] = t_page_obj
        ctx["is_paginated"] = t_paginator.num_pages > 1
        ctx["trucks"] = t_list
        ctx["trucks_count"] = t_paginator.count  # total filtrado (no solo página)

        # ---------------- CAJAS ----------------
        boxes_qs = self._apply_deleted_flags(ReeferBox)
        boxes_qs = self._filter_boxes(boxes_qs)

        b_paginator, b_page_obj, b_list = self._paginate(
            boxes_qs,
            page_param="bpage",
            page_size_param="bpage_size",
            default_size=10,
        )

        ctx["b_paginator"] = b_paginator
        ctx["b_page_obj"] = b_page_obj
        ctx["b_is_paginated"] = b_paginator.num_pages > 1
        ctx["boxes"] = b_list
        ctx["boxes_count"] = b_paginator.count  # total filtrado

        # Barra de búsqueda
        ctx["search_form"] = TruckSearchForm(self.request.GET or None)

        return ctx


# ====== CRUD Camiones ======

class TruckCreateView(CreateView):
    model = Truck
    form_class = TruckForm
    template_name = "trucks/trucks_form.html"
    success_url = reverse_lazy("trucks:list")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Camión creado correctamente.")
        return resp


class TruckUpdateView(UpdateView):
    model = Truck
    form_class = TruckForm
    template_name = "trucks/trucks_form.html"
    success_url = reverse_lazy("trucks:list")

    def get_queryset(self):
        return Truck.objects.all()

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Camión actualizado correctamente.")
        return resp


class TruckDetailView(DetailView):
    model = Truck
    template_name = "trucks/trucks_detail.html"
    context_object_name = "truck"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        truck = self.object
        ctx["orders_workshop"] = truck.ordenes_taller.filter(deleted=False).order_by("-fecha_entrada")
        return ctx


class TruckSoftDeleteView(DeleteView):
    model = Truck
    template_name = "trucks/trucks_confirm_delete.html"
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


# ====== CRUD Cajas ======

class ReeferBoxCreateView(CreateView):
    model = ReeferBox
    form_class = ReeferBoxForm
    template_name = "trucks/reeferbox_form.html"
    success_url = reverse_lazy("trucks:list")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Caja refrigerada creada correctamente.")
        return resp


class ReeferBoxUpdateView(UpdateView):
    model = ReeferBox
    form_class = ReeferBoxForm
    template_name = "trucks/reeferbox_form.html"
    success_url = reverse_lazy("trucks:list")

    def get_queryset(self):
        return ReeferBox.objects.all()

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Caja refrigerada actualizada correctamente.")
        return resp


class ReeferBoxDetailView(DetailView):
    model = ReeferBox
    template_name = "trucks/reeferbox_detail.html"
    context_object_name = "box"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        box = self.object
        ctx["orders_workshop"] = box.ordenes_taller.filter(deleted=False).order_by("-fecha_entrada")
        return ctx


class ReeferBoxSoftDeleteView(DeleteView):
    model = ReeferBox
    template_name = "trucks/reeferbox_confirm_delete.html"
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
