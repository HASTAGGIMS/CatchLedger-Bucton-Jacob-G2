from django.urls import path

from . import views

app_name = "deliveries"

urlpatterns = [
    path("", views.delivery_list, name="delivery_list"),
    path("new/", views.delivery_create, name="delivery_create"),
    path("<int:pk>/", views.delivery_detail, name="delivery_detail"),
    path("<int:pk>/edit/", views.delivery_edit, name="delivery_edit"),
    path("<int:pk>/void/", views.delivery_void, name="delivery_void"),
]
