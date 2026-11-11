
# File: apps/companies/models.py

from django.db import models
from django.utils import timezone


class Company(models.Model):

    name = models.CharField(
        max_length=200,
        unique=True,
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
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name

    def soft_delete(self, reason=""):
        """
        Mark the company as deleted without removing it
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
        Restore a previously soft-deleted company.
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
