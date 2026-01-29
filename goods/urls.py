# mercancias/urls.py
from django.urls import path
from . import views

app_name = "mercancias"

urlpatterns = [
    path("", views.MercanciaListView.as_view(), name="list"),
    path("nuevo/", views.MercanciaCreateView.as_view(), name="create"),
    path("<int:pk>/editar/", views.MercanciaUpdateView.as_view(), name="update"),
    path("<int:pk>/", views.MercanciaDetailView.as_view(), name="detail"),
    path("<int:pk>/eliminar/", views.MercanciaSoftDeleteView.as_view(), name="delete"),
]