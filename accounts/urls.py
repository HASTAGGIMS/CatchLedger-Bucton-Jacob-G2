from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.CatchLedgerLoginView.as_view(), name="login"),
    path("logout/", views.CatchLedgerLogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/recorder/", views.dashboard_recorder, name="dashboard_recorder"),
    path("dashboard/cashier/", views.dashboard_cashier, name="dashboard_cashier"),
    path("dashboard/manager/", views.dashboard_manager, name="dashboard_manager"),
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("password/change/", views.PasswordChangeView.as_view(), name="password_change"),
    path("manage/users/", views.user_list, name="user_list"),
    path("manage/users/<int:pk>/edit/", views.user_edit, name="user_edit"),
]
