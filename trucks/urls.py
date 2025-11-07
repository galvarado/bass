# trucks/urls.py
from django.urls import path
from .views import (
    TruckReeferCombinedListView, 
    TruckCreateView, TruckUpdateView, TruckDetailView, TruckSoftDeleteView,
    ReeferBoxCreateView, ReeferBoxUpdateView, ReeferBoxDetailView, ReeferBoxSoftDeleteView,
)


app_name = "trucks"

urlpatterns = [
    path("", TruckReeferCombinedListView.as_view(), name="list"),

    # Camiones
    path("create/", TruckCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", TruckUpdateView.as_view(), name="update"),
    path("<int:pk>/detail/", TruckDetailView.as_view(), name="detail"),
    path("<int:pk>/delete/", TruckSoftDeleteView.as_view(), name="delete"),

    # Cajas
    path("reeferboxes/create/", ReeferBoxCreateView.as_view(), name="reeferbox_create"),
    path("reeferboxes/<int:pk>/edit/", ReeferBoxUpdateView.as_view(), name="reeferbox_update"),
    path("reeferboxes/<int:pk>/detail/", ReeferBoxDetailView.as_view(), name="reeferbox_detail"),
    path("reeferboxes/<int:pk>/delete/", ReeferBoxSoftDeleteView.as_view(), name="reeferbox_delete"),
]
