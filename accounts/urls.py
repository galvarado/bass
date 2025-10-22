from django.urls import path
from .views import profile_detail, profile_edit, ChangePasswordView, ChangePasswordDoneView

urlpatterns = [
    path("profile/", profile_detail, name="profile"),
    path("profile/edit/", profile_edit, name="profile_edit"),
    path("password/change/", ChangePasswordView.as_view(), name="password_change"),
    path("password/change/done/", ChangePasswordDoneView.as_view(), name="password_change_done"),
]