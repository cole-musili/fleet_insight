
# File: apps/vehicles/views.py

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.shortcuts import render, redirect, get_object_or_404

from .models import Vehicle
from .forms import VehicleForm
from apps.companies.models import Company


def record_list(request):
    # Only show active trucks.
    qs = Vehicle.objects.filter(
        is_deleted=False
    ).select_related("company")

    # Search
    q = request.GET.get("q", "").strip()

    if q:
        qs = qs.filter(
            Q(registration_number__icontains=q)
            | Q(company__name__icontains=q)
            | Q(make__icontains=q)
            | Q(model__icontains=q)
        )

    # Company filter
    company_filter = request.GET.get("company", "").strip()

    if company_filter:
        if company_filter.isdigit():
            qs = qs.filter(
                company_id=int(company_filter),
                company__is_deleted=False,
            )
        else:
            company_filter = ""

    # Sorting
    allowed_sorting = {
        "registration_number": "registration_number",
        "-registration_number": "-registration_number",
        "company": "company__name",
        "-company": "-company__name",
        "make": "make",
        "-make": "-make",
        "model": "model",
        "-model": "-model",
    }

    sort = request.GET.get("sort", "registration_number")

    if sort not in allowed_sorting:
        sort = "registration_number"

    qs = qs.order_by(allowed_sorting[sort], "id")

    # Summary statistics
    active_trucks = Vehicle.objects.filter(
        is_deleted=False
    )

    total_trucks = active_trucks.count()

    companies_with_trucks = (
        active_trucks
        .values("company_id")
        .distinct()
        .count()
    )

    total_makes = (
        active_trucks
        .exclude(make__isnull=True)
        .exclude(make__exact="")
        .values("make")
        .distinct()
        .count()
    )

    # Active companies for filter dropdown
    companies = Company.objects.filter(
        is_deleted=False
    ).order_by("name")

    # Pagination
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "records": page_obj,
        "page_obj": page_obj,
        "q": q,
        "sort": sort,
        "companies": companies,
        "company_filter": company_filter,
        "total_trucks": total_trucks,
        "companies_with_trucks": companies_with_trucks,
        "total_makes": total_makes,
        "page_title": "Truck Register",
    }

    return render(request, "vehicles/list.html", context)


def record_create(request):
    form = VehicleForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        vehicle = form.save()

        messages.success(
            request,
            f"{vehicle.registration_number} was registered successfully."
        )

        return redirect("vehicles_list")

    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Register New Truck",
            "cancel_url": "/trucks/",
        },
    )


def record_edit(request, pk):
    obj = get_object_or_404(
        Vehicle,
        pk=pk,
        is_deleted=False,
    )

    form = VehicleForm(request.POST or None, instance=obj)

    if request.method == "POST" and form.is_valid():
        vehicle = form.save()

        messages.success(
            request,
            f"{vehicle.registration_number} was updated successfully."
        )

        return redirect("vehicles_list")

    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Edit Truck",
            "cancel_url": "/trucks/",
        },
    )


def record_delete(request, pk):
    obj = get_object_or_404(
        Vehicle,
        pk=pk,
        is_deleted=False,
    )

    if request.method == "POST":
        reason = request.POST.get(
            "reason",
            "Removed from the active truck register."
        ).strip()

        try:
            obj.soft_delete(reason=reason)

            messages.success(
                request,
                f"{obj.registration_number} was moved to the Recycle Bin."
            )

        except Exception as exc:
            messages.error(
                request,
                f"Unable to remove truck: {exc}"
            )

        return redirect("vehicles_list")

    return render(
        request,
        "shared/confirm_delete.html",
        {
            "object": obj,
            "page_title": "Remove Truck",
        },
    )
