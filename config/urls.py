
# File: config/urls.py
# Use this file in place of your existing project-level urls.py.

from django.contrib import admin
from django.urls import path, include
from apps.reports import views as report_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # Dashboard
    path("", report_views.dashboard, name="dashboard"),

    # Fleet Management
    path("companies/", include("apps.companies.urls")),
    path("trucks/", include("apps.vehicles.urls")),
    path("drivers/", include("apps.drivers.urls")),
    path("access-cards/", include("apps.access_cards.urls")),
    path("assignments/", include("apps.assignments.urls")),

    # Data Management
    path("imports/", include("apps.imports.urls")),

    # Reports
    path("reports/", include("apps.reports.urls")),

    # System Management
    path("deletion-center/", include("apps.deletion_center.urls")),
]
