from django.urls import path
from . import views
urlpatterns = [
    path("", views.record_list, name="access_cards_list"),
    path("add/", views.record_create, name="access_cards_add"),
    path("<int:pk>/edit/", views.record_edit, name="access_cards_edit"),
    path("<int:pk>/delete/", views.record_delete, name="access_cards_delete"),
]
