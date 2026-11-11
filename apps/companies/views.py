
# File: apps/companies/views.py

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render, redirect, get_object_or_404

from .models import Company
from .forms import CompanyForm


def record_list(request):
    """
    Display active companies with search, sorting and pagination.
    """

    qs = (
        Company.objects
        .filter(is_deleted=False)
        .annotate(
            truck_count=Count(
                "vehicles",
                filter=Q(vehicles__is_deleted=False),
                distinct=True,
            ),
            driver_count=Count(
                "drivers",
                filter=Q(drivers__is_deleted=False),
                distinct=True,
            ),
        )
    )

    # Search
    q = request.GET.get("q", "").strip()

    if q:
        qs = qs.filter(name__icontains=q)

    # Sorting
    allowed_sorting = {
        "name": "name",
        "-name": "-name",
        "trucks": "truck_count",
        "-trucks": "-truck_count",
        "drivers": "driver_count",
        "-drivers": "-driver_count",
    }

    sort = request.GET.get("sort", "name")

    if sort not in allowed_sorting:
        sort = "name"

    qs = qs.order_by(allowed_sorting[sort], "id")

    # Summary statistics
    total_companies = Company.objects.filter(is_deleted=False).count()
    total_trucks = sum(item.truck_count for item in qs)
    total_drivers = sum(item.driver_count for item in qs)

    # Pagination
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "records": page_obj,
        "page_obj": page_obj,
        "q": q,
        "sort": sort,
        "total_companies": total_companies,
        "total_trucks": total_trucks,
        "total_drivers": total_drivers,
        "page_title": "Company Register",
    }

    return render(request, "companies/list.html", context)


def record_create(request):
    form = CompanyForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        company = form.save()

        messages.success(
            request,
            f"{company.name} was added successfully."
        )

        return redirect("companies_list")

    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Register New Company",
            "cancel_url": "/companies/",
        },
    )


def record_edit(request, pk):
    obj = get_object_or_404(
        Company,
        pk=pk,
        is_deleted=False,
    )

    form = CompanyForm(request.POST or None, instance=obj)

    if request.method == "POST" and form.is_valid():
        company = form.save()

        messages.success(
            request,
            f"{company.name} was updated successfully."
        )

        return redirect("companies_list")

    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Edit Company",
            "cancel_url": "/companies/",
        },
    )


def record_delete(request, pk):
    obj = get_object_or_404(
        Company,
        pk=pk,
        is_deleted=False,
    )

    if request.method == "POST":
        reason = request.POST.get(
            "reason",
            "Removed from the active company register."
        ).strip()

        try:
            obj.soft_delete(reason=reason)

            messages.success(
                request,
                f"{obj.name} was moved to the recycle bin."
            )

        except Exception as exc:
            messages.error(
                request,
                f"Unable to remove company: {exc}"
            )

        return redirect("companies_list")

    return render(
        request,
        "shared/confirm_delete.html",
        {
            "object": obj,
            "page_title": "Remove Company",
        },
    )
