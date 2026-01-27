# warehouse/views.py

from django.contrib import messages
from django.db.models import Q, Exists, OuterRef
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView, View
from django.db import transaction
from decimal import Decimal
from django.forms import inlineformset_factory
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

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

from common.mixins import AlmacenRequiredMixin



class SparePartListView(AlmacenRequiredMixin, ListView):
    """
    Lista combinada (tabs) de:
      - Refacciones (spage)
      - Compras (ppage)
      - Pagos (paypage)
    Búsqueda: q aplica a los 3
    """
    model = SparePart
    template_name = "warehouse/list.html"
    context_object_name = "spareparts"
    paginate_by = None  # manual

    # ---------- helpers ----------
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

    def _q_tokens(self):
        q = (self.request.GET.get("q") or "").strip()
        return q.split() if q else []

    # ---------- filtros ----------
    def _filter_spareparts(self, qs):
        for token in self._q_tokens():
            qs = qs.filter(
                Q(code__icontains=token) |
                Q(name__icontains=token) |
                Q(description__icontains=token)
            )
        return qs.order_by("name")

    def _filter_purchases(self, qs):
        # ajusta campos si tu modelo difiere
        for token in self._q_tokens():
            qs = qs.filter(
                Q(invoice_number__icontains=token) |
                Q(notes__icontains=token) |
                Q(supplier__nombre__icontains=token)
            )
        return qs.select_related("supplier").order_by("-date", "-created_at", "-id")

    def _filter_payments(self, qs):
        for token in self._q_tokens():
            qs = qs.filter(
                Q(reference__icontains=token) |
                Q(notes__icontains=token) |
                Q(method__icontains=token) |
                Q(supplier__nombre__icontains=token)
            )
        return qs.select_related("supplier").order_by("-date", "-created_at", "-id")

    # ---------- main ----------
    def get_queryset(self):
        qs = SparePart.objects.filter(deleted=False)
        qs = self._filter_spareparts(qs)
        self._spareparts_qs = qs
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        ctx["tab"] = self.request.GET.get("tab") or "spareparts"
        ctx["search_form"] = SparePartSearchForm(self.request.GET or None)

        # ---------- Refacciones ----------
        sp_paginator, sp_page_obj, sp_list = self._paginate(
            self._spareparts_qs,
            page_param="spage",
            page_size_param="spage_size",
            default_size=10,
        )
        ctx["sp_paginator"] = sp_paginator
        ctx["sp_page_obj"] = sp_page_obj
        ctx["sp_is_paginated"] = sp_paginator.num_pages > 1
        ctx["spareparts"] = sp_list
        ctx["spareparts_count"] = sp_paginator.count

        # ---------- Compras ----------
        purchases_qs = SparePartPurchase.objects.filter(deleted=False)
        purchases_qs = self._filter_purchases(purchases_qs)

        p_paginator, p_page_obj, p_list = self._paginate(
            purchases_qs,
            page_param="ppage",
            page_size_param="ppage_size",
            default_size=10,
        )
        ctx["p_paginator"] = p_paginator
        ctx["p_page_obj"] = p_page_obj
        ctx["p_is_paginated"] = p_paginator.num_pages > 1
        ctx["purchases"] = p_list
        ctx["purchases_count"] = p_paginator.count

        # ---------- Pagos ----------
        payments_qs = SupplierPayment.objects.filter(deleted=False)
        payments_qs = self._filter_payments(payments_qs)

        pay_paginator, pay_page_obj, pay_list = self._paginate(
            payments_qs,
            page_param="paypage",
            page_size_param="paypage_size",
            default_size=10,
        )
        ctx["pay_paginator"] = pay_paginator
        ctx["pay_page_obj"] = pay_page_obj
        ctx["pay_is_paginated"] = pay_paginator.num_pages > 1
        ctx["payments"] = pay_list
        ctx["payments_count"] = pay_paginator.count

        return ctx

class SparePartCreateView(AlmacenRequiredMixin, CreateView):
    model = SparePart
    form_class = SparePartForm
    template_name = "warehouse/sparepart_form.html"
    success_url = reverse_lazy("warehouse:sparepart_list")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Refacción creada correctamente.")
        return resp


class SparePartUpdateView(AlmacenRequiredMixin, UpdateView):
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


class SparePartDetailView(AlmacenRequiredMixin, DetailView):
    model = SparePart
    template_name = "warehouse/sparepart_detail.html"
    context_object_name = "part"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["movements"] = self.object.movements.filter(deleted=False).order_by("-date")
        return ctx


class SparePartSoftDeleteView(AlmacenRequiredMixin, DeleteView):
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


class SparePartPurchaseCreateView(AlmacenRequiredMixin, CreateView):
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


class SparePartPurchaseDetailView(AlmacenRequiredMixin, DetailView):
    model = SparePartPurchase
    template_name = "warehouse/purchase_detail.html"
    context_object_name = "purchase"

    def get_queryset(self):
        return SparePartPurchase.objects.filter(deleted=False)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = self.object.items.all().order_by("id")
        return ctx


class SparePartPurchaseUpdateStatusView(AlmacenRequiredMixin, UpdateView):
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


class SupplierPaymentCreateView(AlmacenRequiredMixin, CreateView):
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


class SupplierPaymentDetailView(AlmacenRequiredMixin, DetailView):
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
