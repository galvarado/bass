# warehouse/forms.py
from django import forms
from django.forms import inlineformset_factory

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
        fields = ["supplier_name", "invoice_number", "date", "notes"]
        widgets = {
            "supplier_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nombre del proveedor"}
            ),
            "invoice_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Factura / Folio"}
            ),
            "date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "notes": forms.Textarea(
                attrs={"class": "form-control", "rows": 2, "placeholder": "Notas de la compra"}
            ),
        }


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
