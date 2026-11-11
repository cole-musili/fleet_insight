# File: apps/assignments/models.py

from django.db import models
from django.utils import timezone

from apps.drivers.models import Driver
from apps.vehicles.models import Vehicle


class DriverTruckAssignment(models.Model):

    driver = models.ForeignKey(
        Driver,
        on_delete=models.PROTECT,
        related_name="truck_assignments",
    )

    truck = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name="driver_assignments",
    )

    date_from = models.DateField()

    date_until = models.DateField(
        null=True,
        blank=True,
        help_text="Leave blank if this assignment is ongoing.",
    )

    notes = models.TextField(
        blank=True,
    )

    # Soft deletion fields
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    deleted_reason = models.TextField(
        blank=True,
    )

    class Meta:
        ordering = ["-date_from"]

    def __str__(self):
        return f"{self.driver} → {self.truck}"

    def soft_delete(self, reason=""):
        """
        Mark the assignment as deleted without permanently
        removing its history.
        """

        if not self.is_deleted:
            self.is_deleted = True
            self.deleted_at = timezone.now()
            self.deleted_reason = reason

            self.save(
                update_fields=[
                    "is_deleted",
                    "deleted_at",
                    "deleted_reason",
                ]
            )

    def restore(self):
        """
        Restore a previously soft-deleted assignment.
        """

        if self.is_deleted:
            self.is_deleted = False
            self.deleted_at = None
            self.deleted_reason = ""

            self.save(
                update_fields=[
                    "is_deleted",
                    "deleted_at",
                    "deleted_reason",
                ]
            )

    @property
    def is_active(self):
        return not self.is_deleted