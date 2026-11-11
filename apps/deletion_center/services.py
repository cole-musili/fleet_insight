
# File: apps/deletion_center/services.py

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.companies.models import Company
from apps.vehicles.models import Vehicle
from apps.drivers.models import Driver
from apps.access_cards.models import AccessCard
from apps.assignments.models import DriverTruckAssignment
from apps.imports.models import ImportBatch

from .models import DeletionOperation, DeletionRecord


# Delete dependent records before the records they reference.
DELETION_ORDER = {
    AccessCard: 10,
    DriverTruckAssignment: 20,
    Vehicle: 30,
    Driver: 40,
    Company: 50,
}

DATASET_MODELS = {
    "trucks": [DriverTruckAssignment, Vehicle],
    "people": [AccessCard, DriverTruckAssignment, Driver],
    "companies": [Company],
    "all": [
        AccessCard,
        DriverTruckAssignment,
        Vehicle,
        Driver,
        Company,
    ],
}


def _authenticated_user(user):
    if user and getattr(user, "is_authenticated", False):
        return user
    return None


def _object_label(obj):
    return str(obj)[:255]


def _create_operation(
    action,
    scope,
    target_label,
    reason="",
    user=None,
    total_records=0,
):
    return DeletionOperation.objects.create(
        action=action,
        scope=scope,
        target_label=target_label,
        reason=reason,
        initiated_by=_authenticated_user(user),
        total_records=total_records,
        status="pending",
    )


def _record_action(operation, obj, action, reason="", user=None):
    content_type = ContentType.objects.get_for_model(
        obj,
        for_concrete_model=False,
    )

    return DeletionRecord.objects.create(
        operation=operation,
        content_type=content_type,
        object_id=obj.pk,
        object_label=_object_label(obj),
        action=action,
        reason=reason,
        performed_by=_authenticated_user(user),
    )


def _finish_operation(operation, successful, failed=0, details=None):
    operation.successful_records = successful
    operation.failed_records = failed
    operation.completed_at = timezone.now()

    if failed and successful:
        operation.status = "partial"
    elif failed:
        operation.status = "failed"
    else:
        operation.status = "completed"

    if details is not None:
        operation.details = details

    operation.save(
        update_fields=[
            "successful_records",
            "failed_records",
            "completed_at",
            "status",
            "details",
        ]
    )

    return operation


def soft_delete_object(obj, reason="", user=None):
    """Move one active record to the Recycle Bin and audit the action."""

    if not hasattr(obj, "soft_delete"):
        raise ValidationError("This record does not support soft deletion.")

    with transaction.atomic():
        locked_obj = obj.__class__.objects.select_for_update().get(pk=obj.pk)

        if getattr(locked_obj, "is_deleted", False):
            raise ValidationError("This record is already in the Recycle Bin.")

        operation = _create_operation(
            action="soft_delete",
            scope="individual",
            target_label=_object_label(locked_obj),
            reason=reason,
            user=user,
            total_records=1,
        )

        locked_obj.soft_delete(reason=reason)

        _record_action(
            operation,
            locked_obj,
            "soft_delete",
            reason,
            user,
        )

        _finish_operation(operation, successful=1)

    return operation


def soft_delete_queryset(
    queryset,
    reason="",
    user=None,
    scope="bulk",
    target_label="Selected records",
):
    """Soft-delete a selection and audit each successful record."""

    objects = list(queryset)

    operation = _create_operation(
        action="soft_delete",
        scope=scope,
        target_label=target_label,
        reason=reason,
        user=user,
        total_records=len(objects),
    )

    successful = 0
    failed = 0
    errors = []

    for obj in objects:
        try:
            with transaction.atomic():
                locked_obj = obj.__class__.objects.select_for_update().get(
                    pk=obj.pk
                )

                if getattr(locked_obj, "is_deleted", False):
                    raise ValidationError("Record is already deleted.")

                if not hasattr(locked_obj, "soft_delete"):
                    raise ValidationError("Record does not support soft deletion.")

                locked_obj.soft_delete(reason=reason)

                _record_action(
                    operation,
                    locked_obj,
                    "soft_delete",
                    reason,
                    user,
                )

            successful += 1

        except Exception as exc:
            failed += 1
            errors.append({
                "record": _object_label(obj),
                "error": str(exc)[:300],
            })

    return _finish_operation(
        operation,
        successful,
        failed,
        details={"errors": errors},
    )


def restore_deleted_record(record_id, user=None):
    """Restore a record using its original soft-delete audit entry."""

    audit_record = DeletionRecord.objects.select_related(
        "content_type"
    ).get(
        pk=record_id,
        action="soft_delete",
    )

    obj = audit_record.content_object

    if obj is None:
        raise ValidationError(
            "The original record no longer exists and cannot be restored."
        )

    if not hasattr(obj, "restore"):
        raise ValidationError("This record does not support restoration.")

    with transaction.atomic():
        locked_obj = obj.__class__.objects.select_for_update().get(pk=obj.pk)

        if not getattr(locked_obj, "is_deleted", False):
            raise ValidationError("This record is not currently deleted.")

        operation = _create_operation(
            action="restore",
            scope="individual",
            target_label=audit_record.object_label,
            reason="Restored from the Recycle Bin.",
            user=user,
            total_records=1,
        )

        locked_obj.restore()

        _record_action(
            operation,
            locked_obj,
            "restore",
            "Restored from the Recycle Bin.",
            user,
        )

        _finish_operation(operation, successful=1)

    return operation


def permanently_delete_object(
    obj,
    reason="",
    user=None,
    operation=None,
):
    """Permanently delete one soft-deleted record and retain its audit."""

    with transaction.atomic():
        locked_obj = obj.__class__.objects.select_for_update().get(pk=obj.pk)

        if not getattr(locked_obj, "is_deleted", False):
            raise ValidationError(
                "Only records in the Recycle Bin can be permanently deleted."
            )

        if operation is None:
            operation = _create_operation(
                action="permanent_delete",
                scope="individual",
                target_label=_object_label(locked_obj),
                reason=reason,
                user=user,
                total_records=1,
            )

        label = _object_label(locked_obj)
        content_type = ContentType.objects.get_for_model(
            locked_obj,
            for_concrete_model=False,
        )
        object_id = locked_obj.pk

        # Database PROTECT constraints are deliberately preserved.
        locked_obj.delete()

        DeletionRecord.objects.create(
            operation=operation,
            content_type=content_type,
            object_id=object_id,
            object_label=label,
            action="permanent_delete",
            reason=reason,
            performed_by=_authenticated_user(user),
        )

    if operation.scope == "individual":
        _finish_operation(operation, successful=1)

    return operation


def permanently_delete_queryset(
    queryset,
    reason="",
    user=None,
    scope="bulk",
    target_label="Selected records",
):
    """Permanently delete selected records already in the Recycle Bin."""

    objects = list(queryset)
    objects.sort(key=lambda obj: DELETION_ORDER.get(type(obj), 100))

    operation = _create_operation(
        action="permanent_delete",
        scope=scope,
        target_label=target_label,
        reason=reason,
        user=user,
        total_records=len(objects),
    )

    successful = 0
    failed = 0
    errors = []

    for obj in objects:
        try:
            permanently_delete_object(
                obj,
                reason=reason,
                user=user,
                operation=operation,
            )
            successful += 1

        except Exception as exc:
            failed += 1
            errors.append({
                "record": _object_label(obj),
                "error": str(exc)[:300],
            })

    return _finish_operation(
        operation,
        successful,
        failed,
        details={"errors": errors},
    )


def soft_delete_category(model, reason="", user=None):
    """Move every active record in one supported category to the Recycle Bin."""

    if model not in DELETION_ORDER:
        raise ValidationError("This category is not supported.")

    queryset = model.objects.filter(is_deleted=False)

    return soft_delete_queryset(
        queryset,
        reason=reason,
        user=user,
        scope="category",
        target_label=f"All active {model._meta.verbose_name_plural}",
    )


def permanently_delete_dataset(dataset, reason="", user=None):
    """Permanently delete only already-soft-deleted records in a dataset."""

    models = DATASET_MODELS.get(dataset)

    if models is None:
        raise ValidationError("Unknown dataset selected.")

    objects = []

    for model in models:
        objects.extend(
            list(model.objects.filter(is_deleted=True))
        )

    objects.sort(key=lambda obj: DELETION_ORDER.get(type(obj), 100))

    operation = _create_operation(
        action="permanent_delete",
        scope="dataset",
        target_label=f"Deleted records in {dataset} dataset",
        reason=reason,
        user=user,
        total_records=len(objects),
    )

    successful = 0
    failed = 0
    errors = []

    for obj in objects:
        try:
            permanently_delete_object(
                obj,
                reason=reason,
                user=user,
                operation=operation,
            )
            successful += 1

        except Exception as exc:
            failed += 1
            errors.append({
                "record": _object_label(obj),
                "error": str(exc)[:300],
            })

    return _finish_operation(
        operation,
        successful,
        failed,
        details={"errors": errors},
    )


def permanently_delete_import_batch(batch_id, reason="", user=None):
    """Delete only records explicitly tracked as created by an import batch."""

    batch = ImportBatch.objects.get(pk=batch_id)

    created_records = list(
        batch.created_records.select_related("content_type")
    )

    tracked_objects = []

    for created_record in created_records:
        obj = created_record.content_object

        if obj is not None:
            tracked_objects.append(obj)

    tracked_objects.sort(
        key=lambda obj: DELETION_ORDER.get(type(obj), 100)
    )

    operation = _create_operation(
        action="permanent_delete",
        scope="batch",
        target_label=f"Import batch: {batch.filename}",
        reason=reason,
        user=user,
        total_records=len(tracked_objects),
    )

    successful = 0
    failed = 0
    errors = []

    for obj in tracked_objects:
        try:
            # Import cleanup is restricted to tracked, soft-deleted objects.
            if not getattr(obj, "is_deleted", False):
                raise ValidationError(
                    "The tracked record must first be moved to the Recycle Bin."
                )

            permanently_delete_object(
                obj,
                reason=reason,
                user=user,
                operation=operation,
            )
            successful += 1

        except Exception as exc:
            failed += 1
            errors.append({
                "record": _object_label(obj),
                "error": str(exc)[:300],
            })

    batch_retained = True

    if failed == 0:
        batch.delete()
        batch_retained = False

    return _finish_operation(
        operation,
        successful,
        failed,
        details={
            "batch_id": batch.pk,
            "batch_retained": batch_retained,
            "errors": errors,
        },
    )
