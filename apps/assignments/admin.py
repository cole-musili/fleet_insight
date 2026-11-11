from django.contrib import admin
from .models import DriverTruckAssignment

@admin.register(DriverTruckAssignment)
class DriverTruckAssignmentAdmin(admin.ModelAdmin):
    list_display = ("driver", "truck", "date_from", "date_until")
    list_filter = ("date_from", "date_until")
    search_fields = ("driver__name", "truck__registration_number")
