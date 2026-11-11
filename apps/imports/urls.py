
# File: apps/imports/urls.py

from django.urls import path
from . import views


urlpatterns = [

    # Import Centre: upload and preview spreadsheet
    path(
        "",
        views.import_upload,
        name="data_import",
    ),

    # Save corrections made in the preview table
    path(
        "update-preview/",
        views.update_preview,
        name="update_preview",
    ),

    # Confirm and process valid records
    path(
        "confirm/",
        views.import_confirm,
        name="import_confirm",
    ),

]
