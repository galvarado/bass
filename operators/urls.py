from django.urls import path
from . import views

app_name = "operators"

urlpatterns = [
    path("", views.OperatorListView.as_view(), name="list"),
    path("nuevo/", views.OperatorCreateView.as_view(), name="create"),
    path("<int:pk>/editar/", views.OperatorUpdateView.as_view(), name="update"),
    path("<int:pk>/", views.OperatorDetailView.as_view(), name="detail"),
    path("<int:pk>/eliminar/", views.OperatorSoftDeleteView.as_view(), name="delete"),
]