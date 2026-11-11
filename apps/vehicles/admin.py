from django.contrib import admin
from .models import Vehicle

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "company", "make", "model")
    list_filter = ("company", "make")
    search_fields = ("registration_number", "company__name", "make", "model")
