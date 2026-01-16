# warehouse/views.py

from django.contrib import messages
from django.db.models import Q, Exists, OuterRef
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView, View
from django.db import transaction
from decimal import Decimal
from django.forms import inlineformset_factory

from .models import SparePart, SparePartPurchase, SparePartMovement, SupplierPayment, SupplierPaymentAllocation
from .forms import (
    SparePartForm,
    SparePartSearchForm,
    SparePartPurchaseForm,
    SparePartPurchaseItemFormSet,
    SparePartPurchaseStatusForm,
    SupplierPaymentForm,
    SupplierPaymentAllocationForm
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

        ctx["payments"] = (
            SupplierPayment.objects.filter(deleted=False)
            .select_related("supplier")
            .order_by("-date", "-created_at", "-id")
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
        self.object = purchase

        # Guardar partidas
        items = formset.save(commit=False)
        saved_items = []

        for item in items:
            # Saltar renglones totalmente vacíos
            if not item.spare_part or not item.quantity:
                continue

            item.purchase = purchase
            item.deleted = False
            item.save()
            saved_items.append(item)

        # === set status según total ===
        threshold = Decimal("10000.00")
        total = purchase.total or Decimal("0")

        if total >= threshold:
            purchase.status = SparePartPurchase.Status.SUBMITTED
        else:
            purchase.status = SparePartPurchase.Status.APPROVED

        purchase.save(update_fields=["status", "updated_at"])

        # === crear movimientos SOLO si quedó APPROVED ===
        if purchase.status == SparePartPurchase.Status.APPROVED:
            supplier_name = purchase.supplier.nombre if purchase.supplier else "—"
            for item in saved_items:
                SparePartMovement.objects.create(
                    spare_part=item.spare_part,
                    movement_type="PURCHASE",
                    quantity=item.quantity,   # positiva
                    unit_cost=item.unit_price,
                    purchase_item=item,
                    description=f"Compra #{purchase.id} - {supplier_name}",
                )
            messages.success(self.request, "Compra registrada y aprobada (inventario actualizado).")
        else:
            messages.success(self.request, "Compra registrada y enviada a aprobación (inventario pendiente).")

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

class SparePartPurchaseUpdateStatusView(UpdateView):
    model = SparePartPurchase
    form_class = SparePartPurchaseStatusForm
    template_name = "warehouse/purchase_form.html"
    success_url = reverse_lazy("warehouse:sparepart_list")

    def get_queryset(self):
        return SparePartPurchase.objects.filter(deleted=False)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_status_edit"] = True
        ctx["items"] = self.object.items.filter(deleted=False).order_by("id")
        ctx["item_formset"] = None
        return ctx

    @transaction.atomic
    def form_valid(self, form):
        purchase = self.object

        # guarda el nuevo status
        resp = super().form_valid(form)

        purchase.refresh_from_db()

        # ✅ Si está APPROVED, aseguramos movimientos (sin duplicar)
        if purchase.status == SparePartPurchase.Status.APPROVED:
            supplier_name = purchase.supplier.nombre if purchase.supplier else "—"

            # Solo items sin movimiento
            items_qs = purchase.items.filter(deleted=False).annotate(
                has_move=Exists(
                    SparePartMovement.objects.filter(
                        deleted=False,
                        movement_type="PURCHASE",
                        purchase_item=OuterRef("pk"),
                    )
                )
            ).filter(has_move=False)

            created = 0
            for item in items_qs:
                SparePartMovement.objects.create(
                    spare_part=item.spare_part,
                    movement_type="PURCHASE",
                    quantity=item.quantity,
                    unit_cost=item.unit_price,
                    purchase_item=item,
                    description=f"Compra #{purchase.id} - {supplier_name}",
                )
                created += 1

            if created:
                messages.success(self.request, f"Estatus actualizado. Inventario aplicado ({created} movimiento(s)).")
            else:
                messages.success(self.request, "Estatus actualizado. Inventario ya estaba aplicado.")
        else:
            messages.success(self.request, "Estatus de compra actualizado.")

        return resp

SupplierPaymentAllocationFormSet = inlineformset_factory(
    SupplierPayment,
    SupplierPaymentAllocation,
    form=SupplierPaymentAllocationForm,
    extra=3,
    can_delete=False,
)

class SupplierPaymentCreateView(CreateView):
    model = SupplierPayment
    form_class = SupplierPaymentForm
    template_name = "warehouse/payment_form.html"
    success_url = reverse_lazy("warehouse:sparepart_list")

    def _get_supplier_id(self):
        raw = (self.request.POST.get("supplier") or self.request.GET.get("supplier") or "").strip()
        if not raw or not raw.isdigit():
            return None
        return int(raw)

    def get_initial(self):
        initial = super().get_initial()
        supplier_id = self._get_supplier_id()
        if supplier_id:
            initial["supplier"] = supplier_id
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        supplier_id = self._get_supplier_id()

        # ✅ Si el supplier viene definido (GET), bloquear el campo
        if supplier_id:
            form.fields["supplier"].disabled = True

        return form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        supplier_id = self._get_supplier_id()

        alloc_formset = kwargs.get("alloc_formset")
        if alloc_formset is None:
            if self.request.POST:
                alloc_formset = SupplierPaymentAllocationFormSet(
                    self.request.POST,
                    prefix="alloc",
                    form_kwargs={"supplier_id": supplier_id},
                )
            else:
                alloc_formset = SupplierPaymentAllocationFormSet(
                    prefix="alloc",
                    form_kwargs={"supplier_id": supplier_id},
                )

        ctx["alloc_formset"] = alloc_formset
        ctx["supplier_locked"] = bool(supplier_id)
        return ctx

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        self.object = None
        supplier_id = self._get_supplier_id()

        form = self.get_form()
        alloc_formset = SupplierPaymentAllocationFormSet(
            self.request.POST,
            prefix="alloc",
            form_kwargs={"supplier_id": supplier_id},
        )

        if not (form.is_valid() and alloc_formset.is_valid()):
            messages.error(self.request, "Por favor corrige los errores del pago.")
            return self.render_to_response(self.get_context_data(form=form, alloc_formset=alloc_formset))

        # ✅ sumar aplicado + exigir al menos 1
        total_applied = Decimal("0.00")
        valid_allocs = 0

        for f in alloc_formset.forms:
            cd = getattr(f, "cleaned_data", None) or {}
            purchase = cd.get("purchase")
            amt = cd.get("amount_applied")

            if not purchase and not amt:
                continue

            if purchase and amt and amt > 0:
                valid_allocs += 1
                total_applied += amt

        if valid_allocs == 0:
            messages.error(self.request, "Debes aplicar el pago al menos a una compra.")
            return self.render_to_response(self.get_context_data(form=form, alloc_formset=alloc_formset))

        payment = form.save(commit=False)

        # ✅ FORZAR supplier desde GET (seguridad)
        if supplier_id:
            payment.supplier_id = supplier_id

        # ✅ monto siempre calculado
        payment.amount = total_applied
        payment.save()
        self.object = payment

        allocs = alloc_formset.save(commit=False)
        for a in allocs:
            if not a.purchase_id or not a.amount_applied:
                continue
            a.payment = payment
            a.deleted = False
            a.save()

        messages.success(self.request, "Pago registrado correctamente.")
        return HttpResponseRedirect(self.get_success_url())

class SupplierPaymentDetailView(DetailView):
    model = SupplierPayment
    template_name = "warehouse/payment_detail.html"
    context_object_name = "payment"

    def get_queryset(self):
        return (
            SupplierPayment.objects.filter(deleted=False)
            .select_related("supplier")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["allocations"] = (
            SupplierPaymentAllocation.objects.filter(deleted=False, payment=self.object)
            .select_related("purchase", "purchase__supplier")
            .order_by("id")
        )
        return ctx