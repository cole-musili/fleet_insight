# File: apps/access_cards/models.py

from django.db import models
from django.utils import timezone

from apps.drivers.models import Driver


class AccessCard(models.Model):

    driver = models.ForeignKey(
        Driver,
        on_delete=models.PROTECT,
        related_name="access_cards",
    )

    identifier = models.CharField(
        max_length=100,
        unique=True,
        help_text="RFID card number; stored as text to preserve leading zeros.",
    )

    date_from = models.DateField(
        verbose_name="Date From",
    )

    date_until = models.DateField(
        verbose_name="Date Until / Expiry",
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
        return f"{self.identifier} - {self.driver.name}"

    @property
    def access_status(self):
        today = timezone.localdate()

        if today < self.date_from:
            return "Not yet active"

        if today > self.date_until:
            return "Expired"

        return "Active"

    def soft_delete(self, reason=""):
        """
        Mark the access card as deleted without permanently
        removing it from the database.
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
        Restore a previously soft-deleted access card.
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