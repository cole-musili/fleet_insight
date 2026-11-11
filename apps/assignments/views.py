from django.contrib import messages
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from .models import DriverTruckAssignment
from .forms import AssignmentForm

def record_list(request):
    qs = DriverTruckAssignment.objects.all()
    q = request.GET.get("q","").strip()
    if q:
        qs = qs.filter(Q(driver__name__icontains=q)|Q(truck__registration_number__icontains=q))
    sort = request.GET.get("sort","")
    allowed = {
        "companies": ["name","-name"],
        "vehicles": ["registration_number","-registration_number","company__name","make","model"],
        "drivers": ["name","-name","organization__name","occupation"],
        "access_cards": ["identifier","-identifier","date_from","date_until","-date_until"],
        "assignments": ["date_from","-date_from","driver__name","truck__registration_number"],
    }["assignments"]
    if sort in allowed:
        qs = qs.order_by(sort)
    return render(request, "assignments/list.html", {"records":qs, "q":q, "sort":sort, "page_title":"Driver–truck assignment Register"})

def record_create(request):
    form = AssignmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Driver–truck assignment saved successfully.")
        return redirect("assignments_list")
    return render(request, "shared/form.html", {"form":form, "page_title":"Add Driver–truck assignment", "cancel_url":"/assignments/"})

def record_edit(request, pk):
    obj = get_object_or_404(DriverTruckAssignment, pk=pk)
    form = AssignmentForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Driver–truck assignment updated successfully.")
        return redirect("assignments_list")
    return render(request, "shared/form.html", {"form":form, "page_title":"Edit Driver–truck assignment", "cancel_url":"/assignments/"})

def record_delete(request, pk):
    obj = get_object_or_404(DriverTruckAssignment, pk=pk)
    if request.method == "POST":
        try:
            obj.delete()
            messages.success(request, "Driver–truck assignment deleted.")
        except Exception:
            messages.error(request, "This record is linked to other records and cannot be deleted.")
        return redirect("assignments_list")
    return render(request, "shared/confirm_delete.html", {"object":obj, "page_title":"Delete Driver–truck assignment"})
