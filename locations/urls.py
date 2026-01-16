from django.urls import path
from . import views

app_name = "locations"

urlpatterns = [
    path("", views.LocationListView.as_view(), name="list"),
    path("create/", views.LocationCreateView.as_view(), name="create"),
    path("<int:pk>/", views.LocationDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.LocationUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.LocationSoftDeleteView.as_view(), name="delete"),
    path("routes/create/", views.RouteCreateView.as_view(), name="routes_create"),
    path("routes/<int:pk>/", views.RouteDetailView.as_view(), name="routes_detail"),
    path("routes/<int:pk>/edit/", views.RouteUpdateView.as_view(), name="routes_edit"),
    path("routes/<int:pk>/delete/", views.RouteSoftDeleteView.as_view(), name="routes_delete"),
    path("ajax/locations-by-client/", views.ajax_locations_by_client, name="ajax_locations_by_client"),

]
