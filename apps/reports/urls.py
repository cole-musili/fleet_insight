
# File: apps/reports/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="reports_dashboard"),
    path("excel/", views.export_excel, name="export_excel"),
    path("pdf/", views.export_pdf, name="export_pdf"),
]
