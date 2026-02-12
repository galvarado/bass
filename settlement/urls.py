# settlement/urls.py
from django.urls import path
from . import views

app_name = "settlement"

urlpatterns = [
    path(
        "por-liquidar/",
        views.CompletedTripsForSettlementListView.as_view(),
        name="completed_trips",
    ),
    path(
        "",
        views.SettlementListView.as_view(),
        name="list",
    ),
    path(
        "nuevo/",
        views.SettlementCreateView.as_view(),
        name="create",
    ),
    path(
        "<int:pk>/",
        views.SettlementDetailView.as_view(),
        name="detail",
    ),
    path(
        "<int:pk>/editar/",
        views.SettlementUpdateView.as_view(),
        name="update",
    ),
    path(
        "<int:pk>/asignar-viajes/",
        views.SettlementAssignTripsView.as_view(),
        name="assign_trips",
    ),
    path(
        "<int:pk>/marcar-lista/",
        views.SettlementMarkReadyView.as_view(),
        name="mark_ready",
    ),
    path("ajax/trip-evidences/<int:trip_id>/",views.AjaxTripEvidencesView.as_view(), name="ajax_trip_evidences"),
    path("ajax/trip-approval/<int:trip_id>/", views.AjaxTripApprovalDecisionView.as_view(), name="ajax_trip_approval"),
    path("ajax/trip-pricing/<int:trip_load_id>/<int:trip_baja_id>/",views.AjaxTripPricingForSettlementView.as_view(), name="ajax_trip_pricing"),

]

