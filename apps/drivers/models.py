# File: apps/drivers/models.py

from django.db import models
from django.utils import timezone

from apps.companies.models import Company


class Driver(models.Model):

    name = models.CharField(
        max_length=200,
    )

    mobile_number = models.CharField(
        max_length=30,
        blank=True,
    )

    organization = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="drivers",
    )

    occupation = models.CharField(
        max_length=100,
        default="Driver",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
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
        ordering = ["name"]

    def __str__(self):
        return self.name

    def soft_delete(self, reason=""):
        """
        Mark the driver as deleted without removing the
        database record or its related records.
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
        Restore a previously soft-deleted driver.
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