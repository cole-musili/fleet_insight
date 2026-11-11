from django.contrib import admin
from .models import Driver

@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("name", "mobile_number", "organization", "occupation")
    list_filter = ("organization", "occupation")
    search_fields = ("name", "mobile_number", "organization__name")
