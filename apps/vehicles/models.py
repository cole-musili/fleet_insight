# File: apps/vehicles/models.py

from django.db import models
from django.utils import timezone

from apps.companies.models import Company


class Vehicle(models.Model):

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="vehicles",
    )

    registration_number = models.CharField(
        max_length=30,
        unique=True,
        verbose_name="REG.NO",
    )

    make = models.CharField(
        max_length=100,
    )

    model = models.CharField(
        max_length=100,
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
        ordering = ["registration_number"]
        verbose_name = "Truck"
        verbose_name_plural = "Trucks"

    def __str__(self):
        return f"{self.registration_number} - {self.make} {self.model}"

    def soft_delete(self, reason=""):
        """
        Mark the vehicle as deleted without removing it
        from the database.
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
        Restore a previously soft-deleted vehicle.
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