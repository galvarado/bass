# suppliers/urls.py
from django.urls import path
from .views import (
    SupplierListView, SupplierCreateView, SupplierUpdateView,
    SupplierDetailView, SupplierSoftDeleteView
)

app_name = "suppliers"

urlpatterns = [
    path("", SupplierListView.as_view(), name="list"),
    path("nuevo/", SupplierCreateView.as_view(), name="create"),
    path("<int:pk>/", SupplierDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", SupplierUpdateView.as_view(), name="update"),
    path("<int:pk>/eliminar/", SupplierSoftDeleteView.as_view(), name="delete"),
]
