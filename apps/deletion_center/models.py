
# File: apps/deletion_center/models.py

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class DeletionOperation(models.Model):
    """
    Records a complete deletion or restoration operation.

    One operation can affect one record or many records.
    """

    ACTION_CHOICES = [
        ("soft_delete", "Move to Recycle Bin"),
        ("restore", "Restore Records"),
        ("permanent_delete", "Permanent Deletion"),
    ]

    SCOPE_CHOICES = [
        ("individual", "Individual Record"),
        ("bulk", "Bulk Records"),
        ("category", "Entire Category"),
        ("batch", "Import Batch"),
        ("dataset", "Entire Dataset"),
        ("recycle_bin", "Recycle Bin Cleanup"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("partial", "Partially Completed"),
        ("failed", "Failed"),
    ]

    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
    )

    scope = models.CharField(
        max_length=30,
        choices=SCOPE_CHOICES,
    )

    target_label = models.CharField(
        max_length=255,
        help_text="Description of the records or dataset affected.",
    )

    reason = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    total_records = models.PositiveIntegerField(default=0)
    successful_records = models.PositiveIntegerField(default=0)
    failed_records = models.PositiveIntegerField(default=0)

    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional operation information.",
    )

    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deletion_operations",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Deletion Operation"
        verbose_name_plural = "Deletion Operations"

        indexes = [
            models.Index(
                fields=["action", "status"],
                name="del_op_action_status_idx",
            ),
            models.Index(
                fields=["created_at"],
                name="del_op_created_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_action_display()} - "
            f"{self.target_label} - "
            f"{self.get_status_display()}"
        )


class DeletionRecord(models.Model):
    """
    Records the action performed on an individual database object.

    GenericForeignKey allows the audit trail to cover records from
    different applications without adding a separate ForeignKey
    for every model.

    The content_type and object_id remain available even after
    the original object has been permanently deleted.
    """

    ACTION_CHOICES = [
        ("soft_delete", "Moved to Recycle Bin"),
        ("restore", "Restored"),
        ("permanent_delete", "Permanently Deleted"),
    ]

    operation = models.ForeignKey(
        DeletionOperation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="records",
    )

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name="deletion_audit_records",
    )

    object_id = models.PositiveBigIntegerField()

    content_object = GenericForeignKey(
        "content_type",
        "object_id",
    )

    object_label = models.CharField(
        max_length=255,
        help_text="Saved description of the affected record.",
    )

    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
    )

    reason = models.TextField(blank=True)

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deletion_records",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Deletion Audit Record"
        verbose_name_plural = "Deletion Audit Records"

        indexes = [
            models.Index(
                fields=["content_type", "object_id"],
                name="del_record_object_idx",
            ),
            models.Index(
                fields=["action", "created_at"],
                name="del_record_action_date_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_action_display()} - "
            f"{self.object_label}"
        )
