
# File: apps/access_cards/views.py

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import AccessCard
from .forms import AccessCardForm


def record_list(request):
    today = timezone.localdate()

    # Only show cards that have not been soft-deleted.
    qs = (
        AccessCard.objects
        .filter(is_deleted=False)
        .select_related("driver", "driver__organization")
    )

    # Search
    q = request.GET.get("q", "").strip()

    if q:
        qs = qs.filter(
            Q(identifier__icontains=q)
            | Q(driver__name__icontains=q)
            | Q(driver__mobile_number__icontains=q)
            | Q(driver__organization__name__icontains=q)
        )

    # Status filter
    status_filter = request.GET.get("status", "").strip()

    if status_filter == "active":
        qs = qs.filter(
            date_from__lte=today,
            date_until__gte=today,
        )
    elif status_filter == "expired":
        qs = qs.filter(date_until__lt=today)
    elif status_filter == "upcoming":
        qs = qs.filter(date_from__gt=today)
    elif status_filter:
        status_filter = ""

    # Sorting
    allowed_sorting = {
        "identifier": "identifier",
        "-identifier": "-identifier",
        "date_from": "date_from",
        "-date_from": "-date_from",
        "date_until": "date_until",
        "-date_until": "-date_until",
        "driver": "driver__name",
        "-driver": "-driver__name",
    }

    sort = request.GET.get("sort", "date_until")

    if sort not in allowed_sorting:
        sort = "date_until"

    qs = qs.order_by(allowed_sorting[sort], "id")

    # Summary statistics: all active records, regardless of filters.
    all_cards = AccessCard.objects.filter(is_deleted=False)

    total_cards = all_cards.count()

    active_cards = all_cards.filter(
        date_from__lte=today,
        date_until__gte=today,
    ).count()

    expired_cards = all_cards.filter(
        date_until__lt=today
    ).count()

    upcoming_cards = all_cards.filter(
        date_from__gt=today
    ).count()

    # Pagination
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "records": page_obj,
        "page_obj": page_obj,
        "q": q,
        "sort": sort,
        "status_filter": status_filter,
        "total_cards": total_cards,
        "active_cards": active_cards,
        "expired_cards": expired_cards,
        "upcoming_cards": upcoming_cards,
        "today": today,
        "page_title": "RFID Access Card Register",
    }

    return render(request, "access_cards/list.html", context)


def record_create(request):
    form = AccessCardForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        card = form.save()

        messages.success(
            request,
            f"RFID access card {card.identifier} was registered successfully."
        )

        return redirect("access_cards_list")

    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Register RFID Access Card",
            "cancel_url": "/access-cards/",
        },
    )


def record_edit(request, pk):
    obj = get_object_or_404(
        AccessCard,
        pk=pk,
        is_deleted=False,
    )

    form = AccessCardForm(request.POST or None, instance=obj)

    if request.method == "POST" and form.is_valid():
        card = form.save()

        messages.success(
            request,
            f"RFID access card {card.identifier} was updated successfully."
        )

        return redirect("access_cards_list")

    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Edit RFID Access Card",
            "cancel_url": "/access-cards/",
        },
    )


def record_delete(request, pk):
    obj = get_object_or_404(
        AccessCard,
        pk=pk,
        is_deleted=False,
    )

    if request.method == "POST":
        reason = request.POST.get(
            "reason",
            "Removed from the active RFID access card register."
        ).strip()

        try:
            obj.soft_delete(reason=reason)

            messages.success(
                request,
                f"RFID card {obj.identifier} was moved to the Recycle Bin."
            )

        except Exception as exc:
            messages.error(
                request,
                f"Unable to remove RFID card: {exc}"
            )

        return redirect("access_cards_list")

    return render(
        request,
        "shared/confirm_delete.html",
        {
            "object": obj,
            "page_title": "Remove RFID Access Card",
        },
    )
