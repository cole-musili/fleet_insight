
# File: apps/imports/admin.py

import json

from django.contrib import admin
from django.utils.html import format_html

from .models import ImportBatch, ImportRow


class ImportRowInline(admin.TabularInline):
    model = ImportRow
    extra = 0
    can_delete = False
    show_change_link = True

    fields = (
        "sheet_name",
        "row_number",
        "status",
        "duplicate_type",
        "missing_fields",
        "invalid_fields",
    )

    readonly_fields = fields

    ordering = ("sheet_name", "row_number")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = (
        "filename",
        "dataset",
        "status_badge",
        "total_rows",
        "imported_rows",
        "updated_rows",
        "invalid_rows",
        "duplicate_rows",
        "created_at",
    )

    list_filter = (
        "dataset",
        "status",
        "created_at",
    )

    search_fields = (
        "filename",
        "error_summary",
    )

    readonly_fields = (
        "dataset",
        "filename",
        "status",
        "total_rows",
        "valid_rows",
        "missing_rows",
        "invalid_rows",
        "duplicate_rows",
        "imported_rows",
        "updated_rows",
        "skipped_rows",
        "error_summary",
        "created_at",
        "completed_at",
        "success_rate_display",
    )

    fieldsets = (
        (
            "Import Information",
            {
                "fields": (
                    "filename",
                    "dataset",
                    "status",
                    "created_at",
                    "completed_at",
                )
            },
        ),
        (
            "Processing Summary",
            {
                "fields": (
                    "total_rows",
                    "valid_rows",
                    "missing_rows",
                    "invalid_rows",
                    "duplicate_rows",
                    "imported_rows",
                    "updated_rows",
                    "skipped_rows",
                    "success_rate_display",
                )
            },
        ),
        (
            "Errors",
            {
                "fields": ("error_summary",),
            },
        ),
    )

    inlines = [ImportRowInline]

    ordering = ("-created_at",)

    def status_badge(self, obj):
        colors = {
            "preview": "#64748b",
            "processing": "#2563eb",
            "completed": "#15803d",
            "failed": "#dc2626",
            "cancelled": "#64748b",
        }

        color = colors.get(obj.status, "#64748b")

        return format_html(
            '<span style="background:{}; color:white; '
            'padding:4px 9px; border-radius:12px; font-size:12px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def success_rate_display(self, obj):
        return f"{obj.success_rate}%"

    success_rate_display.short_description = "Success Rate"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ImportRow)
class ImportRowAdmin(admin.ModelAdmin):
    list_display = (
        "batch",
        "sheet_name",
        "row_number",
        "status",
        "duplicate_type",
        "created_at",
    )

    list_filter = (
        "status",
        "duplicate_type",
        "batch__dataset",
        "created_at",
    )

    search_fields = (
        "batch__filename",
        "sheet_name",
        "error_message",
    )

    readonly_fields = (
        "batch",
        "sheet_name",
        "row_number",
        "data_display",
        "missing_fields",
        "invalid_fields",
        "duplicate_type",
        "status",
        "error_message",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Source",
            {
                "fields": (
                    "batch",
                    "sheet_name",
                    "row_number",
                )
            },
        ),
        (
            "Spreadsheet Data",
            {
                "fields": ("data_display",),
            },
        ),
        (
            "Validation Results",
            {
                "fields": (
                    "status",
                    "duplicate_type",
                    "missing_fields",
                    "invalid_fields",
                    "error_message",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    ordering = ("-created_at",)

    def data_display(self, obj):
        formatted_data = json.dumps(
            obj.data,
            indent=4,
            ensure_ascii=False,
        )

        return format_html(
            '<pre style="white-space:pre-wrap; max-width:900px;">{}</pre>',
            formatted_data,
        )

    data_display.short_description = "Stored Row Data"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
