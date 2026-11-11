
# File: apps/deletion_center/urls.py

from django.urls import path

from . import views

app_name = "deletion_center"

urlpatterns = [
    path("", views.deletion_dashboard, name="dashboard"),
    path("manage/", views.manage_records, name="manage_records"),
    path("delete-category/", views.delete_category, name="delete_category"),
    path("recycle-bin/", views.recycle_bin, name="recycle_bin"),
    path("history/", views.deletion_history, name="history"),
    path("restore/<int:record_id>/", views.restore_record, name="restore"),
]
