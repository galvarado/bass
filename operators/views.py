from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.views import View 
from django.http import HttpResponseRedirect
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView


from .models import Operator
from .forms import OperatorForm, OperatorSearchForm

class OperatorListView(ListView):
    model = Operator
    template_name = "operators/list.html"
    context_object_name = "operators"   
    paginate_by = 10                    

    def get_queryset(self):
        qs = Operator.objects.filter(deleted=False)

        q = (self.request.GET.get("q") or "").strip()
        status = self.request.GET.get("status", "")

        if q:
            tokens = [t for t in q.split() if t]
            for t in tokens:
                qs = qs.filter(
                    Q(first_name__icontains=t) |
                    Q(last_name_paterno__icontains=t) |
                    Q(last_name_materno__icontains=t) |
                    Q(rfc__icontains=t) |
                    Q(license_number__icontains=t) |
                    Q(email__icontains=t) |
                    Q(phone__icontains=t)
                )

        if status in ("0", "1"):
            qs = qs.filter(active=(status == "1"))

        return qs.order_by("last_name_paterno", "last_name_materno", "first_name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)  # <-- NO reemplaces 'operators' aquí
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
        messages.success(self.request, "Operador creado correctamente.")
        return super().form_valid(form)

class OperatorUpdateView(UpdateView):
    model = Operator
    form_class = OperatorForm
    template_name = "operators/form.html"
    success_url = reverse_lazy("operators:list")

    def form_valid(self, form):
        messages.success(self.request, "Operador actualizado correctamente.")
        return super().form_valid(form)

class OperatorDetailView(DetailView):
    model = Operator
    template_name = "operators/detail.html"
    context_object_name = "op"

class OperatorSoftDeleteView(DeleteView):
    model = Operator
    template_name = "operators/confirm_delete.html"
    success_url = reverse_lazy("operators:list")

    def get_queryset(self):
        # evita mostrar confirmación de algo ya eliminado
        return Operator.objects.filter(deleted=False)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.deleted = True
        self.object.save(update_fields=["deleted"])
        messages.success(
            request,
            f"Operador {self.object.first_name} {self.object.last_name_paterno} eliminado."
        )
        return HttpResponseRedirect(self.get_success_url())