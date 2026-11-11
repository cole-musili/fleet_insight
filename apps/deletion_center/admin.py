# File: apps/deletion_center/admin.py

from django.contrib import admin

from .models import DeletionOperation, DeletionRecord


class DeletionRecordInline(admin.TabularInline):
    model = DeletionRecord
    extra = 0
    can_delete = False
    readonly_fields = (
        "content_type",
        "object_id",
        "object_label",
        "action",
        "reason",
        "performed_by",
        "created_at",
    )


@admin.register(DeletionOperation)
class DeletionOperationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "action",
        "scope",
        "target_label",
        "status",
        "total_records",
        "successful_records",
        "failed_records",
        "initiated_by",
        "created_at",
    )

    list_filter = (
        "action",
        "scope",
        "status",
        "created_at",
    )

    search_fields = (
        "target_label",
        "reason",
        "initiated_by__username",
    )

    readonly_fields = (
        "created_at",
        "completed_at",
    )

    inlines = [DeletionRecordInline]


@admin.register(DeletionRecord)
class DeletionRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "object_label",
        "action",
        "content_type",
        "object_id",
        "performed_by",
        "created_at",
    )

    list_filter = (
        "action",
        "content_type",
        "created_at",
    )

    search_fields = (
        "object_label",
        "reason",
        "performed_by__username",
    )

    readonly_fields = (
        "operation",
        "content_type",
        "object_id",
        "object_label",
        "action",
        "reason",
        "performed_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False