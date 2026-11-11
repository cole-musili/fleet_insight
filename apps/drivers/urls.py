from django.urls import path
from . import views
urlpatterns = [
    path("", views.record_list, name="drivers_list"),
    path("add/", views.record_create, name="drivers_add"),
    path("<int:pk>/edit/", views.record_edit, name="drivers_edit"),
    path("<int:pk>/delete/", views.record_delete, name="drivers_delete"),
]
