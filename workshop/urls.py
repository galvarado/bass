from django.urls import path
from . import views

app_name = "workshop"

urlpatterns = [
    path("", views.WorkshopOrderListView.as_view(), name="list"),
    path("nuevo/", views.WorkshopOrderCreateView.as_view(), name="create"),
    path("<int:pk>/editar/", views.WorkshopOrderUpdateView.as_view(), name="update"),
    path("<int:pk>/", views.WorkshopOrderDetailView.as_view(), name="detail"),
    path("<int:pk>/eliminar/", views.WorkshopOrderSoftDeleteView.as_view(), name="delete"),
]