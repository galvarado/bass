from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect, JsonResponse
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.views.decorators.http import require_GET
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required

from .models import Location, Route
from .forms import LocationForm, LocationSearchForm, RouteForm
from common.mixins import CatalogosRequiredMixin


class LocationListView(CatalogosRequiredMixin, ListView):
    """
    UNA sola pantalla con tabs:
      - tab=routes (default)
      - tab=locations

    Paginación independiente:
      - routes: rpage / rpage_size
      - locations: lpage / lpage_size
    """
    model = Location
    template_name = "locations/list.html"
    context_object_name = "locations"
    paginate_by = None  # paginación manual para ambos

    # ---------------- Helpers ----------------
    def get_active_tab(self):
        tab = (self.request.GET.get("tab") or "").strip()
        return tab if tab in ("routes", "locations") else "routes"

    def _apply_deleted_flags(self, Model):
        show_deleted = self.request.GET.get("show_deleted") == "1"
        show_all = self.request.GET.get("show_all") == "1"

        # si tienes all_objects úsalo
        if hasattr(Model, "all_objects"):
            qs = Model.all_objects.all()
        else:
            qs = Model.objects.all()

        if show_all:
            return qs
        if show_deleted:
            return qs.filter(deleted=True)
        return qs.filter(deleted=False)

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

    # ---------------- Querysets ----------------
    def get_locations_queryset(self):
        qs = self._apply_deleted_flags(Location)

        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()

        if q:
            for token in q.split():
                qs = qs.filter(
                    Q(nombre__icontains=token) |
                    Q(client__nombre__icontains=token)
                )

        # status: "1" activas, "0" eliminadas
        if status == "1":
            qs = qs.filter(deleted=False)
        elif status == "0":
            qs = qs.filter(deleted=True)

        return qs.select_related("client").order_by("client__nombre", "nombre")

    def get_routes_queryset(self):
        qs = self._apply_deleted_flags(Route)

        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()

        if q:
            for token in q.split():
                qs = qs.filter(
                    Q(nombre__icontains=token) |
                    Q(client__nombre__icontains=token) |
                    Q(origen__nombre__icontains=token) |
                    Q(destino__nombre__icontains=token)
                )

        if status == "1":
            qs = qs.filter(deleted=False)
        elif status == "0":
            qs = qs.filter(deleted=True)

        return qs.select_related("client", "origen", "destino").order_by(
            "client__nombre", "origen__nombre", "destino__nombre"
        )

    # ---------------- ListView hooks ----------------
    def get_queryset(self):
        # ListView exige un queryset; usamos locations como "principal" y lo guardamos
        self._locations_qs = self.get_locations_queryset()
        return self._locations_qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        active_tab = self.get_active_tab()
        ctx["active_tab"] = active_tab
        ctx["tab"] = active_tab
        ctx["search_form"] = LocationSearchForm(self.request.GET or None)

        # --------- LOCATIONS paginado (lpage) ---------
        loc_qs = getattr(self, "_locations_qs", None) or self.get_locations_queryset()
        loc_paginator, loc_page_obj, loc_list = self._paginate(
            loc_qs, page_param="lpage", page_size_param="lpage_size", default_size=10
        )
        ctx["locations"] = loc_list
        ctx["locations_paginator"] = loc_paginator
        ctx["locations_page_obj"] = loc_page_obj
        ctx["locations_is_paginated"] = loc_paginator.num_pages > 1
        ctx["locations_count"] = loc_paginator.count

        # --------- ROUTES paginado (rpage) ---------
        routes_qs = self.get_routes_queryset()
        routes_paginator, routes_page_obj, routes_list = self._paginate(
            routes_qs, page_param="rpage", page_size_param="rpage_size", default_size=10
        )
        ctx["routes"] = routes_list
        ctx["routes_paginator"] = routes_paginator
        ctx["routes_page_obj"] = routes_page_obj
        ctx["routes_is_paginated"] = routes_paginator.num_pages > 1
        ctx["routes_count"] = routes_paginator.count

        return ctx


class LocationCreateView(CatalogosRequiredMixin, CreateView):
    model = Location
    form_class = LocationForm
    template_name = "locations/form.html"
    success_url = reverse_lazy("locations:list")

    def get_success_url(self):
        return str(reverse_lazy("locations:list")) + "?tab=locations"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Ubicación creada correctamente.")
        return resp


class LocationUpdateView(CatalogosRequiredMixin, UpdateView):
    model = Location
    form_class = LocationForm
    template_name = "locations/form.html"

    def get_queryset(self):
        return Location.objects.all()

    def get_success_url(self):
        return str(reverse_lazy("locations:list")) + "?tab=locations"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Ubicación actualizada correctamente.")
        return resp


class LocationDetailView(CatalogosRequiredMixin, DetailView):
    model = Location
    template_name = "locations/detail.html"
    context_object_name = "location"

    def get_queryset(self):
        return Location.objects.all()


class LocationSoftDeleteView(CatalogosRequiredMixin, DeleteView):
    model = Location
    template_name = "locations/confirm_delete.html"

    def get_queryset(self):
        return Location.objects.filter(deleted=False)

    def get_success_url(self):
        return str(reverse_lazy("locations:list")) + "?tab=locations"

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete()
        messages.success(request, f"Ubicación «{self.object.nombre}» eliminada correctamente.")
        return HttpResponseRedirect(self.get_success_url())


# =========================
# ROUTES
# =========================

class RouteCreateView(CatalogosRequiredMixin, CreateView):
    model = Route
    form_class = RouteForm
    template_name = "locations/routes_form.html"

    def get_success_url(self):
        return str(reverse_lazy("locations:list")) + "?tab=routes"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Ruta creada correctamente.")
        return resp


class RouteUpdateView(CatalogosRequiredMixin, UpdateView):
    """
    Usa el MISMO template routes/form.html,
    pero en backend SOLO permite actualizar tarifas.
    """
    model = Route
    form_class = RouteForm
    template_name = "locations/routes_form.html"

    def get_queryset(self):
        # si quieres permitir editar tarifas aunque esté eliminada, cambia a Route.objects.all()
        return Route.objects.filter(deleted=False).select_related("client", "origen", "destino")

    def get_success_url(self):
        return str(reverse_lazy("locations:list")) + "?tab=routes"

    def form_valid(self, form):
        # SOLO tarifas
        self.object = form.save(commit=False)
        self.object.tarifa_cliente = form.cleaned_data.get("tarifa_cliente")
        self.object.pago_operador = form.cleaned_data.get("pago_operador")
        self.object.save(update_fields=["tarifa_cliente", "pago_operador"])
        messages.success(self.request, "Tarifas actualizadas correctamente.")
        return HttpResponseRedirect(self.get_success_url())


class RouteDetailView(CatalogosRequiredMixin, DetailView):
    model = Route
    template_name = "locations/routes_detail.html"
    context_object_name = "route"

    def get_queryset(self):
        return Route.objects.all().select_related("client", "origen", "destino")


class RouteSoftDeleteView(CatalogosRequiredMixin, DeleteView):
    model = Route
    template_name = "locations/routes_confirm_delete.html"

    def get_queryset(self):
        return Route.objects.filter(deleted=False)

    def get_success_url(self):
        return str(reverse_lazy("locations:list")) + "?tab=routes"

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete()
        messages.success(request, f"Ruta «{self.object}» eliminada correctamente.")
        return HttpResponseRedirect(self.get_success_url())


@require_GET
@login_required
def ajax_locations_by_client(request):
    """
    Devuelve ubicaciones activas de un cliente (para selects origen/destino en creación).
    """
    client_id = request.GET.get("client")
    if not client_id:
        return JsonResponse({"ok": False, "error": "client requerido"}, status=400)

    qs = (
        Location.objects
        .filter(client_id=client_id, deleted=False)
        .order_by("nombre")
        .values("id", "nombre")
    )

    return JsonResponse({"ok": True, "locations": list(qs)})
