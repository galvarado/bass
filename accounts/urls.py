from django.urls import path
from .views import (profile_detail, profile_edit,UserListView, ChangePasswordView, ChangePasswordDoneView,
                     UserListView, UserCreateView, UserUpdateView, UserDeleteView, UserPasswordSetView,
                     RolesInfoView)

app_name = "accounts"


urlpatterns = [
    path("profile/", profile_detail, name="profile"),
    path("roles/", RolesInfoView.as_view(), name="roles"),
    path("profile/edit/", profile_edit, name="profile_edit"),
    path("password/change/", ChangePasswordView.as_view(), name="password_change"),
    path("password/change/done/", ChangePasswordDoneView.as_view(), name="password_change_done"),
    path("", UserListView.as_view(), name="list"),
    path("create/", UserCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", UserUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", UserDeleteView.as_view(), name="delete"),
    path("<int:pk>/password/", UserPasswordSetView.as_view(), name="password"),
]