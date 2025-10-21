from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.views import View 
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView


from .models import Operator
from .forms import OperatorForm, OperatorSearchForm

class OperatorListView(ListView):
    model = Operator
    template_name = "operators/list.html"
    context_object_name = "operators"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().filter(deleted=False)
        q = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "")
        if q:
            qs = qs.filter(
                Q(last_name_paterno__icontains=q) |
                Q(last_name_materno__icontains=q) |
                Q(rfc__icontains=q) |
                Q(license_number__icontains=q) |
                Q(email__icontains=q) |
                Q(phone__icontains=q)
            )
        if status in ("0", "1"):
            qs = qs.filter(active=(status == "1"))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = OperatorSearchForm(self.request.GET or None)
        return ctx

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

class OperatorSoftDeleteView(View):
    def post(self, request, pk):
        op = get_object_or_404(Operator, pk=pk)
        op.deleted = True
        op.save()
        messages.success(request, f"Operador {op.first_name} {op.last_name} marcado como eliminado.")
        return redirect("operators:list")