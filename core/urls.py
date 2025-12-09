"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from core import views as core_views
from common.views import header_info, lookup_cp
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", core_views.dashboard, name="dashboard"),
    path("accounts/", include("accounts.urls")),
    path("operators/", include("operators.urls", namespace="operators")),
    path("customers/", include("customers.urls", namespace="customers")),
    path("locations/", include("locations.urls", namespace="locations")),
    path("trucks/", include("trucks.urls", namespace="trucks")),
    path("trips/", include("trips.urls", namespace="trips")),
    path("audit/", include("audit.urls")),
    path("workshop/", include("workshop.urls")),
    path("warehouse/", include("warehouse.urls")),
    path("api/utils/header-info/", header_info, name="header_info"),
    path("api/utils/lookup-cp/", lookup_cp, name="lookup_cp"),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)