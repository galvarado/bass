from django.urls import path
from . import views
from .views_carta_porte import CartaPorteEditView, CartaPorteStampedPDFView

app_name = "trips"

urlpatterns = [
    path("", views.TripListView.as_view(), name="list"),
    path("nuevo/", views.TripCreateView.as_view(), name="create"),
    path("<int:pk>/editar/", views.TripUpdateView.as_view(), name="update"),
    path("<int:pk>/evidencia/", views.TripEvidenceView.as_view(), name="evidence"),
    path("<int:pk>/", views.TripDetailView.as_view(), name="detail"),
    path("<int:pk>/eliminar/", views.TripSoftDeleteView.as_view(), name="delete"),
    path("monitoreo/", views.TripBoardView.as_view(), name="board"),
    path("monitoreo/cambiar-status/",views.TripChangeStatusView.as_view(), name="change_status",),
    path("viajes/<int:trip_id>/carta-porte/", views.CartaPorteCreateUpdateView.as_view(), name="carta_porte_form"),
    path("ajax/routes/", views.ajax_routes_by_client, name="ajax_routes_by_client"),
    path("mis-viajes/", views.MyTripListView.as_view(), name="my_list"),
    path("mis-viajes/<int:pk>/", views.MyTripDetailView.as_view(), name="my_detail"),
    path("<int:trip_id>/carta-porte/", CartaPorteEditView.as_view(), name="carta_porte_edit"),
    path("<int:carta_id>/carta-porte/pdf/", CartaPorteStampedPDFView.as_view(), name="carta_porte_pdf"),
]