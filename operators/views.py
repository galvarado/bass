# operators/views.py
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView, View

from .models import Operator
from .forms import OperatorForm, OperatorSearchForm

# Campos que auditarías con tu bitácora (ajústalos a lo que realmente registres)
FIELDS_AUDIT = [
    "nombre", "rfc", "curp", "telefono", "puesto", "status", "deleted",
    "licencia_federal", "licencia_federal_vencimiento",
    "ine", "ine_vencimiento",
    "visa", "visa_vencimiento",
    "pasaporte", "pasaporte_vencimiento",
    "examen_medico", "examen_medico_vencimiento",
    "rcontrol", "rcontrol_vencimiento",
    "antidoping", "antidoping_vencimiento",
]


class OperatorListView(ListView):
    model = Operator
    template_name = "operators/list.html"
    context_object_name = "operators"
    paginate_by = 10

    def get_queryset(self):
        """
        - Por defecto muestra solo no eliminados (deleted=False).
        - Si ?show_deleted=1, muestra solo eliminados.
        - Si ?show_all=1, muestra todos (incluidos eliminados).
        - Soporta status 'ALTA'/'BAJA' y compat con '1'/'0' (1=ALTA, 0=BAJA).
        - Búsqueda en nombre, RFC, CURP, licencia, teléfono, puesto y dirección.
        """
        show_deleted = self.request.GET.get("show_deleted") == "1"
        show_all = self.request.GET.get("show_all") == "1"

        # Managers simplificados:
        # - Operator.objects → todos (admin también lo usa)
        # - Operator.alive → solo no eliminados
        if show_all:
            qs = Operator.objects.all()  # mostrar todo, incluso eliminados
        elif show_deleted:
            qs = Operator.objects.filter(deleted=True)
        else:
            qs = Operator.alive.filter(deleted=False)

        # --- Filtros ---
        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip().upper()

        # Compatibilidad '1'/'0' → 'ALTA'/'BAJA'
        if status in ("1", "0"):
            status = "ALTA" if status == "1" else "BAJA"

        if q:
            for token in q.split():
                qs = qs.filter(
                    Q(nombre__icontains=token) |
                    Q(rfc__icontains=token) |
                    Q(curp__icontains=token) |
                    Q(licencia_federal__icontains=token) 
                )

        if status in ("ALTA", "BAJA"):
            qs = qs.filter(status=status)

        return qs.order_by("nombre")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = OperatorSearchForm(self.request.GET or None)
        return ctx


    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = OperatorSearchForm(self.request.GET or None)
        return ctx

    def get_paginate_by(self, queryset):
        try:
            return int(self.request.GET.get("page_size", self.paginate_by))
        except (TypeError, ValueError):
            return self.paginate_by


class OperatorCreateView(CreateView):
    model = Operator
    form_class = OperatorForm
    template_name = "operators/form.html"
    success_url = reverse_lazy("operators:list")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Operador creado correctamente.")
        return resp


class OperatorUpdateView(UpdateView):
    model = Operator
    form_class = OperatorForm
    template_name = "operators/form.html"
    success_url = reverse_lazy("operators:list")

    def get_queryset(self):
        # Evitar editar eliminados desde esta vista (a menos que lo quieras permitir)
        return Operator.objects.all()

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Operador actualizado correctamente.")
        return resp


class OperatorDetailView(DetailView):
    model = Operator
    template_name = "operators/detail.html"
    context_object_name = "op"

    def get_queryset(self):
        # Permite ver detalle tanto vivos como eliminados
            return Operator.objects.all()



# operators/views.py
class OperatorSoftDeleteView(DeleteView):
    model = Operator
    template_name = "operators/confirm_delete.html"
    success_url = reverse_lazy("operators:list")

    def get_queryset(self):
        # Solo permite eliminar no eliminados
        return Operator.objects.all()

    def delete(self, request, *args, **kwargs):
        """Sobrescribe el borrado físico del DeleteView."""
        self.object = self.get_object()
        self.object.soft_delete() 
        messages.success(request, f"Operador '{self.object.nombre}' eliminado correctamente.")
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        """Redirige post() hacia delete() manualmente."""
        return self.delete(request, *args, **kwargs)
