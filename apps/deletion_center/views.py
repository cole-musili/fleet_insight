
# File: apps/deletion_center/views.py

from functools import wraps

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.companies.models import Company
from apps.vehicles.models import Vehicle
from apps.drivers.models import Driver
from apps.access_cards.models import AccessCard
from apps.assignments.models import DriverTruckAssignment

from .models import DeletionOperation, DeletionRecord
from .services import (
    soft_delete_object,
    soft_delete_queryset,
    soft_delete_category,
    restore_deleted_record,
    permanently_delete_queryset,
)


DELETION_CATEGORIES = {
    "companies": Company,
    "trucks": Vehicle,
    "drivers": Driver,
    "access_cards": AccessCard,
    "assignments": DriverTruckAssignment,
}


def _category_queryset(model, deleted=False):
    queryset = model.objects.filter(is_deleted=deleted)

    if model == Company:
        return queryset.order_by("name")

    if model == Vehicle:
        return queryset.select_related("company").order_by(
            "registration_number"
        )

    if model == Driver:
        return queryset.select_related("organization").order_by("name")

    if model == AccessCard:
        return queryset.select_related(
            "driver",
            "driver__organization",
        ).order_by("identifier")

    if model == DriverTruckAssignment:
        return queryset.select_related(
            "driver",
            "truck",
        ).order_by("-date_from")

    return queryset


def _search_queryset(queryset, model, search):
    if not search:
        return queryset

    if model == Company:
        return queryset.filter(name__icontains=search)

    if model == Vehicle:
        return queryset.filter(
            Q(registration_number__icontains=search)
            | Q(make__icontains=search)
            | Q(model__icontains=search)
            | Q(company__name__icontains=search)
        )

    if model == Driver:
        return queryset.filter(
            Q(name__icontains=search)
            | Q(mobile_number__icontains=search)
            | Q(organization__name__icontains=search)
            | Q(occupation__icontains=search)
        )

    if model == AccessCard:
        return queryset.filter(
            Q(identifier__icontains=search)
            | Q(driver__name__icontains=search)
            | Q(driver__organization__name__icontains=search)
        )

    if model == DriverTruckAssignment:
        return queryset.filter(
            Q(driver__name__icontains=search)
            | Q(truck__registration_number__icontains=search)
        )

    return queryset


@staff_member_required(login_url="/admin/login/")
def deletion_dashboard(request):
    """Display deletion centre statistics and recent operations."""

    models = list(DELETION_CATEGORIES.values())

    recycle_bin_count = sum(
        model.objects.filter(is_deleted=True).count()
        for model in models
    )

    active_record_count = sum(
        model.objects.filter(is_deleted=False).count()
        for model in models
    )

    categories = []

    for key, model in DELETION_CATEGORIES.items():
        categories.append({
            "key": key,
            "label": model._meta.verbose_name_plural.title(),
            "active_count": model.objects.filter(
                is_deleted=False
            ).count(),
            "deleted_count": model.objects.filter(
                is_deleted=True
            ).count(),
        })

    context = {
        "recycle_bin_count": recycle_bin_count,
        "active_record_count": active_record_count,
        "recent_operations": DeletionOperation.objects.select_related(
            "initiated_by"
        )[:10],
        "categories": categories,
    }

    return render(
        request,
        "deletion_center/dashboard.html",
        context,
    )


@staff_member_required(login_url="/admin/login/")
def manage_records(request):
    """Search and select active records for individual or bulk deletion."""

    category = request.GET.get(
        "category",
        request.POST.get("category", "companies"),
    )

    if category not in DELETION_CATEGORIES:
        category = "companies"

    model = DELETION_CATEGORIES[category]
    search = request.GET.get("q", "").strip()

    queryset = _category_queryset(model, deleted=False)
    queryset = _search_queryset(queryset, model, search)

    if request.method == "POST":
        selected_ids = request.POST.getlist("selected_ids")
        reason = request.POST.get("reason", "").strip()
        confirmation = request.POST.get("confirmation", "").strip()

        if not selected_ids:
            messages.error(request, "Select at least one record.")
            return redirect(
                f"/deletion-center/manage/?category={category}"
            )

        if not reason:
            messages.error(request, "Enter a reason for deletion.")
            return redirect(
                f"/deletion-center/manage/?category={category}"
            )

        if confirmation != "MOVE TO RECYCLE BIN":
            messages.error(
                request,
                "Type MOVE TO RECYCLE BIN to confirm this operation.",
            )
            return redirect(
                f"/deletion-center/manage/?category={category}"
            )

        valid_ids = [
            value for value in selected_ids if value.isdigit()
        ]

        selected_queryset = model.objects.filter(
            pk__in=valid_ids,
            is_deleted=False,
        )

        operation = soft_delete_queryset(
            selected_queryset,
            reason=reason,
            user=request.user,
            scope="individual" if len(valid_ids) == 1 else "bulk",
            target_label=(
                f"{model._meta.verbose_name_plural.title()} "
                f"selected for deletion"
            ),
        )

        messages.success(
            request,
            f"Deletion completed: {operation.successful_records} "
            f"record(s) moved to the Recycle Bin; "
            f"{operation.failed_records} failed.",
        )

        return redirect("deletion_center:history")

    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "categories": [
            {
                "key": key,
                "label": model._meta.verbose_name_plural.title(),
            }
            for key, model in DELETION_CATEGORIES.items()
        ],
        "selected_category": category,
        "selected_label": model._meta.verbose_name_plural.title(),
        "search": search,
        "records": page_obj,
        "page_obj": page_obj,
        "total_records": queryset.count(),
    }

    return render(
        request,
        "deletion_center/manage_records.html",
        context,
    )


@staff_member_required(login_url="/admin/login/")
@require_POST
def delete_category(request):
    """Move every active record in a category to the Recycle Bin."""

    category = request.POST.get("category", "")
    reason = request.POST.get("reason", "").strip()
    confirmation = request.POST.get("confirmation", "").strip()

    model = DELETION_CATEGORIES.get(category)

    if model is None:
        messages.error(request, "Invalid deletion category.")
        return redirect("deletion_center:dashboard")

    if not reason:
        messages.error(request, "A reason is required.")
        return redirect("deletion_center:dashboard")

    if confirmation != "DELETE CATEGORY":
        messages.error(
            request,
            "Type DELETE CATEGORY to confirm this operation.",
        )
        return redirect("deletion_center:dashboard")

    try:
        operation = soft_delete_category(
            model,
            reason=reason,
            user=request.user,
        )

        messages.success(
            request,
            f"{operation.successful_records} "
            f"{model._meta.verbose_name_plural} record(s) "
            f"moved to the Recycle Bin. "
            f"{operation.failed_records} failed.",
        )

    except Exception as exc:
        messages.error(request, f"Category deletion failed: {exc}")

    return redirect("deletion_center:history")


@staff_member_required(login_url="/admin/login/")
def recycle_bin(request):
    """Display soft-deleted records from supported categories."""

    deleted_records = []

    for key, model in DELETION_CATEGORIES.items():
        content_type = ContentType.objects.get_for_model(
            model,
            for_concrete_model=False,
        )

        records = _category_queryset(model, deleted=True)

        for obj in records:
            audit_record = DeletionRecord.objects.filter(
                content_type=content_type,
                object_id=obj.pk,
                action="soft_delete",
            ).order_by("-created_at").first()

            deleted_records.append({
                "id": obj.pk,
                "selection_id": f"{key}:{obj.pk}",
                "category": key,
                "category_label": model._meta.verbose_name.title(),
                "label": str(obj),
                "deleted_at": obj.deleted_at,
                "deleted_reason": obj.deleted_reason,
                "audit_record": audit_record,
            })

    deleted_records.sort(
        key=lambda item: item["deleted_at"] or timezone_minimum(),
        reverse=True,
    )

    search = request.GET.get("q", "").strip()

    if search:
        deleted_records = [
            record for record in deleted_records
            if search.lower() in (
                record["label"] + " " +
                record["category_label"] + " " +
                record["deleted_reason"]
            ).lower()
        ]

    if request.method == "POST":
        action = request.POST.get("action", "")
        selected_records = request.POST.getlist("selected_records")
        reason = request.POST.get("reason", "").strip()
        confirmation = request.POST.get("confirmation", "").strip()

        if not selected_records:
            messages.error(request, "Select at least one record.")
            return redirect("deletion_center:recycle_bin")

        if action == "restore":
            successful = 0
            failed = 0

            for audit_id in selected_records:
                if not audit_id.isdigit():
                    failed += 1
                    continue

                try:
                    restore_deleted_record(
                        record_id=int(audit_id),
                        user=request.user,
                    )
                    successful += 1
                except Exception:
                    failed += 1

            messages.success(
                request,
                f"Restored {successful} record(s). "
                f"{failed} record(s) could not be restored.",
            )

            return redirect("deletion_center:recycle_bin")

        if action == "permanent_delete":
            if not reason:
                messages.error(
                    request,
                    "Enter a reason for permanent deletion.",
                )
                return redirect("deletion_center:recycle_bin")

            if confirmation != "PERMANENTLY DELETE":
                messages.error(
                    request,
                    "Type PERMANENTLY DELETE to confirm.",
                )
                return redirect("deletion_center:recycle_bin")

            grouped_ids = {}

            for value in selected_records:
                try:
                    category_key, object_id = value.split(":", 1)

                    if (
                        category_key in DELETION_CATEGORIES
                        and object_id.isdigit()
                    ):
                        grouped_ids.setdefault(category_key, []).append(
                            int(object_id)
                        )
                except ValueError:
                    continue

            successful = 0
            failed = 0

            for category_key, ids in grouped_ids.items():
                model = DELETION_CATEGORIES[category_key]

                operation = permanently_delete_queryset(
                    model.objects.filter(
                        pk__in=ids,
                        is_deleted=True,
                    ),
                    reason=reason,
                    user=request.user,
                    scope="recycle_bin",
                    target_label=(
                        f"Recycle Bin: "
                        f"{model._meta.verbose_name_plural}"
                    ),
                )

                successful += operation.successful_records
                failed += operation.failed_records

            messages.success(
                request,
                f"Permanently deleted {successful} record(s). "
                f"{failed} record(s) could not be deleted. "
                f"Protected relationships were not bypassed.",
            )

            return redirect("deletion_center:history")

        messages.error(request, "Unknown Recycle Bin action.")
        return redirect("deletion_center:recycle_bin")

    return render(
        request,
        "deletion_center/recycle_bin.html",
        {
            "deleted_records": deleted_records,
            "search": search,
        },
    )


def timezone_minimum():
    from datetime import datetime, timezone
    return datetime.min.replace(tzinfo=timezone.utc)


@staff_member_required(login_url="/admin/login/")
def deletion_history(request):
    """Display deletion and restoration audit history."""

    records = DeletionRecord.objects.select_related(
        "operation",
        "content_type",
        "performed_by",
    ).all()

    operations = DeletionOperation.objects.select_related(
        "initiated_by"
    ).all()[:50]

    return render(
        request,
        "deletion_center/deletion_history.html",
        {
            "records": records[:200],
            "operations": operations,
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_POST
def restore_record(request, record_id):
    """Restore a deleted record after explicit confirmation."""

    try:
        restore_deleted_record(
            record_id=record_id,
            user=request.user,
        )

        messages.success(
            request,
            "The record has been restored successfully.",
        )

    except (DeletionRecord.DoesNotExist, ValidationError) as exc:
        messages.error(request, str(exc))

    except Exception:
        messages.error(
            request,
            "The record could not be restored. Check its relationships and try again.",
        )

    return redirect("deletion_center:recycle_bin")
