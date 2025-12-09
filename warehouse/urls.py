# warehouse/urls.py
from django.urls import path
from .views import *
app_name = "warehouse"

urlpatterns = [
    path("", SparePartListView.as_view(), name="sparepart_list"),
    path("nuevo/", SparePartCreateView.as_view(), name="sparepart_create"),
    path("<int:pk>/editar/", SparePartUpdateView.as_view(), name="sparepart_update"),
    path("<int:pk>/", SparePartDetailView.as_view(), name="sparepart_detail"),
    path("<int:pk>/eliminar/", SparePartSoftDeleteView.as_view(), name="sparepart_delete"),
    path("compras/nueva/", SparePartPurchaseCreateView.as_view(), name="purchase_create"),
    path("compras/<int:pk>/", SparePartPurchaseDetailView.as_view(), name="purchase_detail"),
]
