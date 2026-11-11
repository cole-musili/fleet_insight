from django.urls import path
from . import views
urlpatterns = [
    path("", views.record_list, name="companies_list"),
    path("add/", views.record_create, name="companies_add"),
    path("<int:pk>/edit/", views.record_edit, name="companies_edit"),
    path("<int:pk>/delete/", views.record_delete, name="companies_delete"),
]
