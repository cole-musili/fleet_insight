
# File: apps/imports/models.py

from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class ImportBatch(models.Model):
    """
    Stores the details and processing summary of an uploaded import file.
    """

    DATASET_CHOICES = [
        ("trucks", "Trucks"),
        ("people", "People"),
    ]

    STATUS_CHOICES = [
        ("preview", "Preview"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    dataset = models.CharField(
        max_length=30,
        choices=DATASET_CHOICES,
    )

    filename = models.CharField(
        max_length=255,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="preview",
    )

    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    missing_rows = models.PositiveIntegerField(default=0)
    invalid_rows = models.PositiveIntegerField(default=0)
    duplicate_rows = models.PositiveIntegerField(default=0)

    imported_rows = models.PositiveIntegerField(default=0)
    updated_rows = models.PositiveIntegerField(default=0)
    skipped_rows = models.PositiveIntegerField(default=0)

    error_summary = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Import Batch"
        verbose_name_plural = "Import Batches"

    def __str__(self):
        return f"{self.filename} - {self.get_status_display()}"

    @property
    def success_rate(self):
        if self.total_rows == 0:
            return 0

        return round(
            (self.imported_rows + self.updated_rows)
            / self.total_rows * 100,
            2,
        )


class ImportRow(models.Model):
    """
    Stores an individual spreadsheet row and its validation/import status.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("valid", "Valid"),
        ("missing", "Missing Information"),
        ("invalid", "Invalid"),
        ("duplicate", "Duplicate"),
        ("imported", "Imported"),
        ("updated", "Updated"),
        ("skipped", "Skipped"),
        ("failed", "Failed"),
    ]

    DUPLICATE_CHOICES = [
        ("", "Not a Duplicate"),
        ("existing", "Already Exists"),
        ("file", "Duplicate in Uploaded File"),
    ]

    batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.CASCADE,
        related_name="rows",
    )

    sheet_name = models.CharField(
        max_length=255,
        blank=True,
    )

    row_number = models.PositiveIntegerField()

    # Original and corrected spreadsheet values.
    data = models.JSONField(default=dict, blank=True)

    # Field names requiring attention.
    missing_fields = models.JSONField(default=list, blank=True)
    invalid_fields = models.JSONField(default=list, blank=True)

    duplicate_type = models.CharField(
        max_length=20,
        choices=DUPLICATE_CHOICES,
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sheet_name", "row_number"]
        verbose_name = "Import Row"
        verbose_name_plural = "Import Rows"

        constraints = [
            models.UniqueConstraint(
                fields=["batch", "sheet_name", "row_number"],
                name="unique_import_batch_sheet_row",
            )
        ]

        indexes = [
            models.Index(fields=["batch", "status"]),
            models.Index(fields=["batch", "duplicate_type"]),
        ]

    def __str__(self):
        location = f"{self.sheet_name}, row {self.row_number}"
        return f"{self.batch.filename} - {location}"


class ImportCreatedRecord(models.Model):
    """
    Links a record created by an import to its originating batch.

    A single spreadsheet row may create multiple database records.
    For example, a people import can create a Driver and an AccessCard.

    GenericForeignKey allows this model to track records from different
    applications without adding an import_batch ForeignKey to every model.
    """

    batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.CASCADE,
        related_name="created_records",
    )

    row = models.ForeignKey(
        ImportRow,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_records",
    )

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name="fleet_import_created_records",
    )

    object_id = models.PositiveBigIntegerField()

    content_object = GenericForeignKey(
        "content_type",
        "object_id",
    )

    object_label = models.CharField(
        max_length=255,
        blank=True,
        help_text="Readable description of the created database record.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Import Created Record"
        verbose_name_plural = "Import Created Records"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "batch",
                    "content_type",
                    "object_id",
                ],
                name="unique_created_record_per_import_batch",
            )
        ]

        indexes = [
            models.Index(
                fields=["content_type", "object_id"],
                name="import_created_object_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.batch.filename} - "
            f"{self.object_label or self.object_id}"
        )
