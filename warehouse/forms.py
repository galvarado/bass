# warehouse/forms.py
from django import forms
from django.forms import inlineformset_factory

from suppliers.models import Supplier

from .models import (
    SparePart,
    SparePartPurchase,
    SparePartPurchaseItem,
)

class SparePartForm(forms.ModelForm):
    """
    Formulario para crear / editar refacciones.
    """

    class Meta:
        model = SparePart
        fields = [
            "code",
            "name",
            "description",
            "unit",
            "min_stock",
            "notes",
        ]

        widgets = {
            "code": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Código interno / fabricante",
                }
            ),
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nombre de la refacción",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Descripción breve, modelo, aplicación, etc.",
                }
            ),
            "unit": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej. pieza, litro, juego…",
                }
            ),
            "location": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Estante A, Nivel 2, Caja 3…",
                }
            ),
            "min_stock": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Notas internas de almacén",
                }
            ),
        }


class SparePartSearchForm(forms.Form):
    """
    Form de búsqueda para la lista de refacciones.
    Solo un campo 'q' por ahora (código, nombre, descripción).
    """
    q = forms.CharField(
        required=False,
        label="",
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Buscar por código, nombre o descripción…",
            }
        ),
    )

class SparePartPurchaseForm(forms.ModelForm):
    class Meta:
        model = SparePartPurchase
        fields = ["supplier", "invoice_number", "date", "notes"]
        widgets = {
            "supplier": forms.Select(attrs={"class": "form-control"}),
            "invoice_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "Factura / Folio"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Notas de la compra"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Proveedores no borrados
        self.fields["supplier"].queryset = Supplier.alive.all().order_by("nombre")
        self.fields["supplier"].empty_label = "Selecciona proveedor..."

        # Label amigable (tu Supplier no tiene RFC)
        self.fields["supplier"].label_from_instance = lambda s: (s.razon_social or s.nombre)



class SparePartPurchaseItemForm(forms.ModelForm):
    class Meta:
        model = SparePartPurchaseItem
        fields = ["spare_part", "quantity", "unit_price", "notes"]
        widgets = {
            "spare_part": forms.Select(
                attrs={"class": "form-control form-control-sm"}
            ),
            "quantity": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01", "min": "0"}
            ),
            "unit_price": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01", "min": "0"}
            ),
            "notes": forms.TextInput(
                attrs={"class": "form-control form-control-sm", "placeholder": "Notas de la partida"}
            ),
        }


SparePartPurchaseItemFormSet = inlineformset_factory(
    SparePartPurchase,
    SparePartPurchaseItem,
    form=SparePartPurchaseItemForm,
    extra=3,
    can_delete=False,
)


class SparePartPurchaseItemForm(forms.ModelForm):
    class Meta:
        model = SparePartPurchaseItem
        fields = ["spare_part", "quantity", "unit_price", "notes"]
        widgets = {
            "spare_part": forms.Select(
                attrs={"class": "form-control form-control-sm"}
            ),
            "quantity": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01", "min": "0"}
            ),
            "unit_price": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01", "min": "0"}
            ),
            "notes": forms.TextInput(
                attrs={"class": "form-control form-control-sm", "placeholder": "Notas de la partida"}
            ),
        }


SparePartPurchaseItemFormSet = inlineformset_factory(
    SparePartPurchase,
    SparePartPurchaseItem,
    form=SparePartPurchaseItemForm,
    extra=3,
    can_delete=False,  # para empezar simple; luego podemos permitir borrar líneas
)

class SparePartPurchaseStatusForm(forms.ModelForm):
    class Meta:
        model = SparePartPurchase
        fields = ["status"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Solo permitir transición desde SUBMITTED
        if self.instance and self.instance.pk:
            if self.instance.status != "SUBMITTED":
                # No debería ni poder editarse, pero por si llega aquí:
                self.fields["status"].disabled = True

        # Solo mostrar opciones válidas (aprobar / rechazar)
        allowed = {"APPROVED", "REJECTED"}
        self.fields["status"].choices = [
            c for c in self.fields["status"].choices
            if c[0] in allowed
        ]

    def clean_status(self):
        new_status = self.cleaned_data.get("status")

        # Si alguien intenta cambiar sin estar SUBMITTED, bloquea
        if self.instance and self.instance.pk and self.instance.status != "SUBMITTED":
            raise forms.ValidationError("Solo puedes cambiar el estatus cuando la compra está en 'Enviada a aprobación'.")

        # Seguridad extra: solo permitir APPROVED/REJECTED
        if new_status not in {"APPROVED", "REJECTED"}:
            raise forms.ValidationError("Estatus inválido para aprobación.")

        return new_status

from .models import SupplierPayment, SupplierPaymentAllocation

class SupplierPaymentForm(forms.ModelForm):
    class Meta:
        model = SupplierPayment
        fields = ["supplier", "date", "method", "reference", "amount", "notes"]
        widgets = {
            "supplier": forms.Select(attrs={"class": "form-control"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "method": forms.Select(attrs={"class": "form-control"}),
            "reference": forms.TextInput(attrs={"class": "form-control", "placeholder": "Folio / referencia bancaria"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "readonly": "readonly"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self._user = user
        self.fields["amount"].required = False
        self.fields["supplier"].queryset = Supplier.alive.all().order_by("nombre")
        self.fields["supplier"].empty_label = "Selecciona proveedor..."
        self.fields["supplier"].label_from_instance = lambda s: (s.razon_social or s.nombre)

    def save(self, commit=True):
        obj = super().save(commit=False)
        if getattr(obj, "created_by_id", None) is None and getattr(self, "_user", None):
            obj.created_by = self._user
        if commit:
            obj.save()
        return obj

class SupplierPaymentAllocationForm(forms.ModelForm):
    class Meta:
        model = SupplierPaymentAllocation
        fields = ["purchase", "amount_applied"]
        widgets = {
            "purchase": forms.Select(attrs={"class": "form-control form-control-sm"}),
            "amount_applied": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01", "min": "0"}
            ),
        }

    def __init__(self, *args, **kwargs):
        supplier_id = kwargs.pop("supplier_id", None)
        super().__init__(*args, **kwargs)

        # ✅ Normalizar supplier_id por seguridad
        try:
            supplier_id = int(supplier_id)
        except (TypeError, ValueError):
            supplier_id = None

        if not supplier_id:
            # ✅ Sin proveedor: no mostrar compras
            self.fields["purchase"].queryset = SparePartPurchase.objects.none()
            self.fields["purchase"].empty_label = "Selecciona un proveedor primero..."
            return

        qs = (
            SparePartPurchase.objects.filter(
                deleted=False,
                supplier_id=supplier_id,
                status=SparePartPurchase.Status.APPROVED,
            )
            .order_by("-date", "-id")
        )

        self.fields["purchase"].queryset = qs
        self.fields["purchase"].empty_label = "Selecciona compra..."

        def _label(p):
            # Si no tienes balance todavía, cambia a solo total
            return f"Compra #{p.id} | {p.date:%d/%m/%Y} | Total ${p.total:.2f} | Saldo ${p.balance:.2f}"

        self.fields["purchase"].label_from_instance = _label

        # 👇 Etiqueta mostrando total/saldo (si tienes balance)
        def _label(p):
            # OJO: si p.balance no existe aún, quita esa parte
            return f"Compra #{p.id} | {p.date:%d/%m/%Y} | Total ${p.total:.2f} | Saldo ${p.balance:.2f}"

        self.fields["purchase"].label_from_instance = _label
