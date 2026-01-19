# operators/views.py
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.text import slugify
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView

from .models import Operator
from .forms import OperatorForm, OperatorSearchForm

User = get_user_model()

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


def build_base_username(op: Operator) -> str:
    base = (op.rfc or op.curp or op.nombre or "operador").strip()
    base = slugify(base).replace("-", "")
    return base or "operador"


def ensure_unique_username(base: str) -> str:
    username = base[:150]
    if not User.objects.filter(username=username).exists():
        return username

    i = 2
    while True:
        candidate = f"{base[:140]}{i}"
        if not User.objects.filter(username=candidate).exists():
            return candidate
        i += 1


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
        - Búsqueda en nombre, RFC, CURP, licencia.
        """
        show_deleted = self.request.GET.get("show_deleted") == "1"
        show_all = self.request.GET.get("show_all") == "1"

        if show_all:
            qs = Operator.objects.all()
        elif show_deleted:
            qs = Operator.objects.filter(deleted=True)
        else:
            qs = Operator.alive.filter(deleted=False)

        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip().upper()

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

    @transaction.atomic
    def form_valid(self, form):
        # 1) crear operador
        resp = super().form_valid(form)
        op: Operator = self.object

        # 2) si ya trae usuario, no duplicar
        if getattr(op, "user_id", None):
            messages.success(self.request, "Operador creado correctamente (usuario ya asignado).")
            return resp

        # 3) crear user
        username = ensure_unique_username(build_base_username(op))

        user = User.objects.create(
            username=username,
            first_name=(op.nombre or "")[:150],
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )
        user.set_unusable_password()
        user.save()

        # 4) asignar grupo operador
        operador_group, _ = Group.objects.get_or_create(name="operador")
        user.groups.add(operador_group)

        # 5) ligar operador -> user
        op.user = user
        op.save(update_fields=["user"])

        messages.success(
            self.request,
            f"Operador creado correctamente. Usuario '{username}' creado y asignado al grupo OPERADOR."
        )
        return resp


class OperatorUpdateView(UpdateView):
    model = Operator
    form_class = OperatorForm
    template_name = "operators/form.html"
    success_url = reverse_lazy("operators:list")

    def get_queryset(self):
        return Operator.objects.all()

    def form_valid(self, form):
        resp = super().form_valid(form)
        op: Operator = self.object

        # Sync estado del operador -> user.is_active
        # Regla: BAJA o deleted => user inactive
        if getattr(op, "user", None):
            should_be_active = (op.status == "ALTA") and (not op.deleted)
            if op.user.is_active != should_be_active:
                op.user.is_active = should_be_active
                op.user.save(update_fields=["is_active"])

                if should_be_active:
                    messages.info(self.request, "El usuario del operador fue reactivado (ALTA).")
                else:
                    messages.info(self.request, "El usuario del operador fue desactivado (BAJA o eliminado).")

        messages.success(self.request, "Operador actualizado correctamente.")
        return resp



class OperatorDetailView(DetailView):
    model = Operator
    template_name = "operators/detail.html"
    context_object_name = "op"

    def get_queryset(self):
        return Operator.objects.all()


class OperatorSoftDeleteView(DeleteView):
    model = Operator
    template_name = "operators/confirm_delete.html"
    success_url = reverse_lazy("operators:list")

    def get_queryset(self):
        return Operator.objects.all()

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete()

        if getattr(self.object, "user", None):
            if self.object.user.is_active:
                self.object.user.is_active = False
                self.object.user.save(update_fields=["is_active"])

        messages.success(request, f"Operador '{self.object.nombre}' eliminado correctamente.")
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)
