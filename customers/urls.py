from django.urls import path
from . import views

app_name = "Clients"

urlpatterns = [
    path("", views.ClientListView.as_view(), name="list"),
    path("nuevo/", views.ClientCreateView.as_view(), name="create"),
    path("<int:pk>/editar/", views.ClientUpdateView.as_view(), name="update"),
    path("<int:pk>/", views.ClientDetailView.as_view(), name="detail"),
    path("<int:pk>/eliminar/", views.ClientSoftDeleteView.as_view(), name="delete"),
]