
# File: apps/drivers/views.py

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404

from .models import Driver
from .forms import DriverForm
from apps.companies.models import Company


def record_list(request):
    # Only active drivers
    qs = (
        Driver.objects
        .filter(is_deleted=False)
        .select_related("organization")
    )

    # Search
    q = request.GET.get("q", "").strip()

    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(mobile_number__icontains=q)
            | Q(organization__name__icontains=q)
            | Q(occupation__icontains=q)
        )

    # Organization filter
    organization_filter = request.GET.get("organization", "").strip()

    if organization_filter:
        if organization_filter.isdigit():
            qs = qs.filter(
                organization_id=int(organization_filter),
                organization__is_deleted=False,
            )
        else:
            organization_filter = ""

    # Occupation filter
    occupation_filter = request.GET.get("occupation", "").strip()

    if occupation_filter:
        qs = qs.filter(occupation__iexact=occupation_filter)

    # Sorting
    allowed_sorting = {
        "name": "name",
        "-name": "-name",
        "organization": "organization__name",
        "-organization": "-organization__name",
        "occupation": "occupation",
        "-occupation": "-occupation",
    }

    sort = request.GET.get("sort", "name")

    if sort not in allowed_sorting:
        sort = "name"

    qs = qs.order_by(allowed_sorting[sort], "id")

    # Summary statistics
    active_drivers = Driver.objects.filter(is_deleted=False)

    total_drivers = active_drivers.count()

    organizations_with_drivers = (
        active_drivers
        .values("organization_id")
        .distinct()
        .count()
    )

    total_occupations = (
        active_drivers
        .exclude(occupation__isnull=True)
        .exclude(occupation__exact="")
        .values("occupation")
        .distinct()
        .count()
    )

    # Active organizations for the filter
    companies = Company.objects.filter(
        is_deleted=False
    ).order_by("name")

    # Occupations from active drivers only
    occupations = (
        active_drivers
        .exclude(occupation__isnull=True)
        .exclude(occupation__exact="")
        .values_list("occupation", flat=True)
        .distinct()
        .order_by("occupation")
    )

    # Pagination
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "records": page_obj,
        "page_obj": page_obj,
        "q": q,
        "sort": sort,
        "companies": companies,
        "organization_filter": organization_filter,
        "occupations": occupations,
        "occupation_filter": occupation_filter,
        "total_drivers": total_drivers,
        "organizations_with_drivers": organizations_with_drivers,
        "total_occupations": total_occupations,
        "page_title": "Driver Register",
    }

    return render(request, "drivers/list.html", context)


def record_create(request):
    form = DriverForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        driver = form.save()

        messages.success(
            request,
            f"{driver.name} was registered successfully."
        )

        return redirect("drivers_list")

    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Register New Driver",
            "cancel_url": "/drivers/",
        },
    )


def record_edit(request, pk):
    obj = get_object_or_404(
        Driver,
        pk=pk,
        is_deleted=False,
    )

    form = DriverForm(request.POST or None, instance=obj)

    if request.method == "POST" and form.is_valid():
        driver = form.save()

        messages.success(
            request,
            f"{driver.name} was updated successfully."
        )

        return redirect("drivers_list")

    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Edit Driver",
            "cancel_url": "/drivers/",
        },
    )


def record_delete(request, pk):
    obj = get_object_or_404(
        Driver,
        pk=pk,
        is_deleted=False,
    )

    if request.method == "POST":
        reason = request.POST.get(
            "reason",
            "Removed from the active driver register."
        ).strip()

        try:
            obj.soft_delete(reason=reason)

            messages.success(
                request,
                f"{obj.name} was moved to the Recycle Bin."
            )

        except Exception as exc:
            messages.error(
                request,
                f"Unable to remove driver: {exc}"
            )

        return redirect("drivers_list")

    return render(
        request,
        "shared/confirm_delete.html",
        {
            "object": obj,
            "page_title": "Remove Driver",
        },
    )
