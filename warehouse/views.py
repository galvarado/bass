# warehouse/views.py

from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.db import transaction

from .models import SparePart, SparePartPurchase, SparePartMovement
from .forms import (
    SparePartForm,
    SparePartSearchForm,
    SparePartPurchaseForm,
    SparePartPurchaseItemFormSet,
)



class SparePartListView(ListView):
    model = SparePart
    template_name = "warehouse/list.html"
    context_object_name = "spareparts"
    paginate_by = 10

    def get_queryset(self):
        """
        Búsqueda simple:
        - ?q=<texto>
        Filtra en: code, name y description.
        """
        # El manager ya filtra deleted=False, pero dejamos el filtro explícito
        qs = SparePart.objects.filter(deleted=False)

        q = (self.request.GET.get("q") or "").strip()

        if q:
            for token in q.split():
                qs = qs.filter(
                    Q(code__icontains=token)
                    | Q(name__icontains=token)
                    | Q(description__icontains=token)
                )

        return qs.order_by("name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Form de búsqueda (para refacciones)
        ctx["search_form"] = SparePartSearchForm(self.request.GET or None)

        # Compras para la segunda tabla (solo no eliminadas)
        ctx["purchases"] = (
            SparePartPurchase.objects.filter(deleted=False)
            .order_by("-date", "-created_at")
        )
        return ctx

    def get_paginate_by(self, queryset):
        try:
            return int(self.request.GET.get("page_size", self.paginate_by))
        except (TypeError, ValueError):
            return self.paginate_by


class SparePartCreateView(CreateView):
    model = SparePart
    form_class = SparePartForm
    template_name = "warehouse/sparepart_form.html"
    success_url = reverse_lazy("warehouse:sparepart_list")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Refacción creada correctamente.")
        return resp

class SparePartUpdateView(UpdateView):
    model = SparePart
    form_class = SparePartForm
    template_name = "warehouse/sparepart_form.html"
    success_url = reverse_lazy("warehouse:sparepart_list")

    def get_queryset(self):
        return SparePart.objects.all()  # permitir ver incluso eliminados si quieres

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Refacción actualizada correctamente.")
        return resp

class SparePartDetailView(DetailView):
    model = SparePart
    template_name = "warehouse/sparepart_detail.html"
    context_object_name = "part"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["movements"] = self.object.movements.filter(deleted=False).order_by("-date")
        return ctx

class SparePartSoftDeleteView(DeleteView):
    model = SparePart
    template_name = "warehouse/sparepart_confirm_delete.html"
    success_url = reverse_lazy("warehouse:sparepart_list")

    def get_queryset(self):
        return SparePart.objects.filter(deleted=False)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        # usar el método del modelo
        self.object.soft_delete()
        messages.success(
            request,
            f"Refacción '{self.object.name}' eliminada correctamente."
        )
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        # redirige el POST hacia delete()
        return self.delete(request, *args, **kwargs)

class SparePartPurchaseCreateView(CreateView):
    model = SparePartPurchase
    form_class = SparePartPurchaseForm
    template_name = "warehouse/purchase_form.html"
    # 👇 la lista principal de almacén (tabs refacciones/compras)
    success_url = reverse_lazy("warehouse:sparepart_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx["item_formset"] = SparePartPurchaseItemFormSet(
                self.request.POST,
                prefix="items",
            )
        else:
            ctx["item_formset"] = SparePartPurchaseItemFormSet(
                prefix="items",
            )
        return ctx

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        formset = SparePartPurchaseItemFormSet(
            self.request.POST,
            prefix="items",
        )

        if form.is_valid() and formset.is_valid():
            return self.form_valid_with_items(form, formset)
        else:
            return self.form_invalid_with_items(form, formset)

    def form_valid_with_items(self, form, formset):
        # Guardar cabecera
        purchase = form.save()
        # 👇 muy importante para que get_success_url no truene
        self.object = purchase

        # Guardar partidas
        items = formset.save(commit=False)
        for item in items:
            # Saltar renglones totalmente vacíos
            if not item.spare_part or not item.quantity:
                continue

            item.purchase = purchase
            item.deleted = False
            item.save()

            # Movimiento de entrada a inventario
            SparePartMovement.objects.create(
                spare_part=item.spare_part,
                movement_type="PURCHASE",
                quantity=item.quantity,   # positiva
                unit_cost=item.unit_price,
                purchase_item=item,
                description=f"Compra #{purchase.id} - {purchase.supplier_name}",
            )

        messages.success(self.request, "Compra de refacciones registrada correctamente.")
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid_with_items(self, form, formset):
        messages.error(self.request, "Por favor corrige los errores en la compra.")
        return self.render_to_response(
            self.get_context_data(form=form, item_formset=formset)
        )

class SparePartPurchaseDetailView(DetailView):
    model = SparePartPurchase
    template_name = "warehouse/purchase_detail.html"
    context_object_name = "purchase"

    def get_queryset(self):
        return SparePartPurchase.objects.filter(deleted=False)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = self.object.items.all().order_by("id")
        return ctx
