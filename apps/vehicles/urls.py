from django.urls import path
from . import views
urlpatterns = [
    path("", views.record_list, name="vehicles_list"),
    path("add/", views.record_create, name="vehicles_add"),
    path("<int:pk>/edit/", views.record_edit, name="vehicles_edit"),
    path("<int:pk>/delete/", views.record_delete, name="vehicles_delete"),
]
