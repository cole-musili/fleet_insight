from django.urls import path
from . import views
urlpatterns = [
    path("", views.record_list, name="assignments_list"),
    path("add/", views.record_create, name="assignments_add"),
    path("<int:pk>/edit/", views.record_edit, name="assignments_edit"),
    path("<int:pk>/delete/", views.record_delete, name="assignments_delete"),
]
