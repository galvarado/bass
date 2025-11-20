from django.urls import path
from . import views

app_name = "trips"

urlpatterns = [
    path("", views.TripListView.as_view(), name="list"),
    path("nuevo/", views.TripCreateView.as_view(), name="create"),
    path("<int:pk>/editar/", views.TripUpdateView.as_view(), name="update"),
    path("<int:pk>/", views.TripDetailView.as_view(), name="detail"),
    path("<int:pk>/eliminar/", views.TripSoftDeleteView.as_view(), name="delete"),
    path("monitoreo/", views.TripBoardView.as_view(), name="board"),
    path("monitoreo/cambiar-status/",views.TripChangeStatusView.as_view(), name="change_status",
    ),
]