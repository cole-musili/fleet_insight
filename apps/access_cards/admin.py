from django.contrib import admin
from .models import AccessCard

@admin.register(AccessCard)
class AccessCardAdmin(admin.ModelAdmin):
    list_display = ("identifier", "driver", "date_from", "date_until", "status")
    search_fields = ("identifier", "driver__name", "driver__mobile_number")
    list_filter = ("date_from", "date_until")

    @admin.display(description="Access status")
    def status(self, obj):
        return obj.access_status
