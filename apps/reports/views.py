
# File: apps/reports/views.py

from datetime import timedelta
from io import BytesIO
from html import escape

from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    KeepTogether,
)

from apps.companies.models import Company
from apps.vehicles.models import Vehicle
from apps.drivers.models import Driver
from apps.access_cards.models import AccessCard
from apps.assignments.models import DriverTruckAssignment


REPORT_TYPES = [
    ("truck_register", "Truck Register"),
    ("driver_register", "Driver Register"),
    ("rfid_register", "RFID Access Register"),
    ("assignments", "Driver–Truck Assignments"),
    ("company_summary", "Company Summary"),
    ("data_quality", "Data Quality Assessment"),
]


# ---------------------------------------------------------
# SHARED REPORT FILTERING
# ---------------------------------------------------------

def get_report_data(request):

    today = timezone.localdate()

    filters = {
        "company": request.GET.get("company", "").strip(),
        "make": request.GET.get("make", "").strip(),
        "model": request.GET.get("model", "").strip(),
        "rfid_status": request.GET.get("rfid_status", "").strip(),
        "assignment_status": request.GET.get(
            "assignment_status", ""
        ).strip(),
    }

    report_type = request.GET.get(
        "report_type", "truck_register"
    )

    if report_type not in dict(REPORT_TYPES):
        report_type = "truck_register"

    companies = Company.objects.all()

    trucks = Vehicle.objects.select_related("company").all()

    drivers = Driver.objects.select_related("organization").all()

    cards = AccessCard.objects.select_related(
        "driver", "driver__organization"
    ).all()

    assignments = DriverTruckAssignment.objects.select_related(
        "driver",
        "driver__organization",
        "truck",
        "truck__company",
    ).all()

    # Company filter
    if filters["company"]:
        trucks = trucks.filter(company_id=filters["company"])

        drivers = drivers.filter(
            organization_id=filters["company"]
        )

        cards = cards.filter(
            driver__organization_id=filters["company"]
        )

        assignments = assignments.filter(
            truck__company_id=filters["company"],
            driver__organization_id=filters["company"],
        )

    # Truck make and model filters
    if filters["make"]:
        trucks = trucks.filter(make__iexact=filters["make"])
        assignments = assignments.filter(
            truck__make__iexact=filters["make"]
        )

    if filters["model"]:
        trucks = trucks.filter(model__iexact=filters["model"])
        assignments = assignments.filter(
            truck__model__iexact=filters["model"]
        )

    # RFID status filter
    if filters["rfid_status"] == "active":
        cards = cards.filter(
            date_from__lte=today,
            date_until__gte=today,
        )

    elif filters["rfid_status"] == "expired":
        cards = cards.filter(date_until__lt=today)

    elif filters["rfid_status"] == "upcoming":
        cards = cards.filter(date_from__gt=today)

    # Assignment status filter
    if filters["assignment_status"] == "active":
        assignments = assignments.filter(
            date_from__lte=today
        ).filter(
            Q(date_until__isnull=True) |
            Q(date_until__gte=today)
        )

    elif filters["assignment_status"] == "completed":
        assignments = assignments.filter(
            date_until__lt=today
        )

    elif filters["assignment_status"] == "future":
        assignments = assignments.filter(
            date_from__gt=today
        )

    # Company summary
    company_stats = companies.annotate(
        truck_total=Count("vehicles", distinct=True),
        driver_total=Count("drivers", distinct=True),
    ).order_by("name")

    if filters["company"]:
        company_stats = company_stats.filter(
            id=filters["company"]
        )

    # Data quality
    quality = {
        "truck_missing_make": trucks.filter(
            Q(make__isnull=True) | Q(make="")
        ).count(),

        "truck_missing_model": trucks.filter(
            Q(model__isnull=True) | Q(model="")
        ).count(),

        "driver_missing_mobile": drivers.filter(
            Q(mobile_number__isnull=True) |
            Q(mobile_number="")
        ).count(),

        "card_missing_dates": cards.filter(
            Q(date_from__isnull=True) |
            Q(date_until__isnull=True)
        ).count(),
    }

    return {
        "today": today,
        "filters": filters,
        "report_type": report_type,
        "report_title": dict(REPORT_TYPES)[report_type],

        "companies": companies,
        "company_stats": company_stats,

        "trucks": trucks,
        "drivers": drivers,
        "cards": cards,
        "assignments": assignments,

        "quality": quality,

        "total_trucks": trucks.count(),
        "total_drivers": drivers.count(),
        "total_cards": cards.count(),
        "total_assignments": assignments.count(),

        "active_cards": cards.filter(
            date_from__lte=today,
            date_until__gte=today,
        ).count(),

        "expired_cards": cards.filter(
            date_until__lt=today
        ).count(),

        "upcoming_cards": cards.filter(
            date_until__gte=today,
            date_until__lte=today + timedelta(days=30),
        ).count(),

        "active_assignments": assignments.filter(
            date_from__lte=today
        ).filter(
            Q(date_until__isnull=True) |
            Q(date_until__gte=today)
        ).count(),

        "truck_makes": (
            Vehicle.objects.order_by("make")
            .values_list("make", flat=True)
            .distinct()
        ),

        "truck_models": (
            Vehicle.objects.order_by("model")
            .values_list("model", flat=True)
            .distinct()
        ),

        "report_types": REPORT_TYPES,
    }


# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------

def dashboard(request):

    data = get_report_data(request)

    report_type = data["report_type"]

    preview = []

    if report_type == "truck_register":
        preview = data["trucks"][:15]

    elif report_type == "driver_register":
        preview = data["drivers"][:15]

    elif report_type == "rfid_register":
        preview = data["cards"][:15]

    elif report_type == "assignments":
        preview = data["assignments"][:15]

    elif report_type == "company_summary":
        preview = data["company_stats"][:15]

    return render(
        request,
        "reports/dashboard.html",
        {
            **data,
            "preview": preview,
            "generated_at": timezone.localtime(),
        },
    )


# ---------------------------------------------------------
# REPORT DATA PREPARATION
# ---------------------------------------------------------

def get_report_rows(data):

    report_type = data["report_type"]

    if report_type == "truck_register":

        headers = [
            "Company",
            "Registration Number",
            "Make",
            "Model",
        ]

        rows = [
            [
                v.company.name,
                v.registration_number,
                v.make,
                v.model,
            ]
            for v in data["trucks"]
        ]

    elif report_type == "driver_register":

        headers = [
            "Driver Name",
            "Mobile Number",
            "Organization",
            "Occupation",
        ]

        rows = [
            [
                d.name,
                d.mobile_number,
                d.organization.name,
                d.occupation,
            ]
            for d in data["drivers"]
        ]

    elif report_type == "rfid_register":

        headers = [
            "Driver",
            "Mobile",
            "Organization",
            "Occupation",
            "RFID Identifier",
            "Valid From",
            "Valid Until",
            "Access Status",
        ]

        rows = [
            [
                c.driver.name,
                c.driver.mobile_number,
                c.driver.organization.name,
                c.driver.occupation,
                c.identifier,
                c.date_from,
                c.date_until,
                c.access_status,
            ]
            for c in data["cards"]
        ]

    elif report_type == "assignments":

        headers = [
            "Driver",
            "Organization",
            "Truck Registration",
            "Make",
            "Model",
            "Date From",
            "Date Until",
            "Assignment Status",
            "Notes",
        ]

        rows = []

        today = data["today"]

        for a in data["assignments"]:

            if a.date_from > today:
                status = "Future"

            elif a.date_until and a.date_until < today:
                status = "Completed"

            else:
                status = "Active"

            rows.append([
                a.driver.name,
                a.driver.organization.name,
                a.truck.registration_number,
                a.truck.make,
                a.truck.model,
                a.date_from,
                a.date_until or "Ongoing",
                status,
                a.notes,
            ])

    elif report_type == "company_summary":

        headers = [
            "Company",
            "Number of Trucks",
            "Number of Drivers",
        ]

        rows = [
            [
                c.name,
                c.truck_total,
                c.driver_total,
            ]
            for c in data["company_stats"]
        ]

    else:

        headers = [
            "Data Quality Check",
            "Missing Records",
        ]

        rows = [
            ["Trucks missing make", data["quality"]["truck_missing_make"]],
            ["Trucks missing model", data["quality"]["truck_missing_model"]],
            ["Drivers missing mobile", data["quality"]["driver_missing_mobile"]],
            ["RFID records missing dates", data["quality"]["card_missing_dates"]],
        ]

    return headers, rows


# ---------------------------------------------------------
# EXCEL EXPORT
# ---------------------------------------------------------

def export_excel(request):
    """
    Export the currently selected report as a clean data extract.

    The worksheet contains only:
    - Column headers in the first row.
    - Data records from the second row onward.

    No report title, branding, generation timestamp, filter summary,
    merged cells, or decorative report formatting is added.
    """

    data = get_report_data(request)
    headers, rows = get_report_rows(data)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Data"

    # Row 1: column names. Rows 2 onward: actual records.
    sheet.append(headers)

    for row in rows:
        sheet.append(row)

    # Keep the worksheet convenient to inspect without adding report content.
    # These settings do not add extra rows or alter the exported values.
    sheet.freeze_panes = "A2"

    if headers:
        last_column = get_column_letter(len(headers))
        sheet.auto_filter.ref = f"A1:{last_column}{sheet.max_row}"

    response = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

    filename = (
        f"fleet_{data['report_type']}_"
        f"{data['today'].strftime('%Y%m%d')}.xlsx"
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )

    workbook.save(response)
    return response


# ---------------------------------------------------------
# PDF EXPORT
# ---------------------------------------------------------

def export_pdf(request):

    data = get_report_data(request)

    headers, rows = get_report_rows(data)

    buffer = BytesIO()

    wide_reports = {
        "truck_register",
        "rfid_register",
        "assignments",
    }

    page_size = (
        landscape(A4)
        if data["report_type"] in wide_reports
        else A4
    )

    document = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=13 * mm,
        bottomMargin=15 * mm,
        title=data["report_title"],
        author="Fleet Insights",
    )

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="FleetTitle",
            parent=styles["Title"],
            fontSize=20,
            textColor=colors.HexColor("#145A40"),
            alignment=TA_CENTER,
            spaceAfter=5,
        )
    )

    styles.add(
        ParagraphStyle(
            name="FleetCell",
            parent=styles["Normal"],
            fontSize=7,
            leading=9,
        )
    )

    story = [
        Paragraph(
            "FLEET INSIGHTS",
            styles["FleetTitle"],
        ),
        Paragraph(
            escape(data["report_title"]),
            styles["Heading2"],
        ),
        Paragraph(
            "Generated: "
            + timezone.localtime().strftime(
                "%d %B %Y, %H:%M"
            ),
            styles["Normal"],
        ),
        Spacer(1, 10),
    ]

    story.append(
        Paragraph(
            "APPLIED FILTERS",
            styles["Heading3"],
        )
    )

    filter_rows = [
        ["Filter", "Selection"],
        [
            "Company",
            data["filters"]["company"] or "All companies",
        ],
        [
            "Truck make",
            data["filters"]["make"] or "All makes",
        ],
        [
            "Truck model",
            data["filters"]["model"] or "All models",
        ],
        [
            "RFID status",
            data["filters"]["rfid_status"] or "All statuses",
        ],
        [
            "Assignment status",
            data["filters"]["assignment_status"] or "All statuses",
        ],
    ]

    filter_table = Table(
        filter_rows,
        colWidths=[45 * mm, 100 * mm],
    )

    filter_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0), (-1, 0),
                colors.HexColor("#145A40"),
            ),
            (
                "TEXTCOLOR",
                (0, 0), (-1, 0),
                colors.white,
            ),
            (
                "GRID",
                (0, 0), (-1, -1),
                0.35,
                colors.HexColor("#DDE5E0"),
            ),
            (
                "FONTSIZE",
                (0, 0), (-1, -1),
                8,
            ),
            (
                "VALIGN",
                (0, 0), (-1, -1),
                "MIDDLE",
            ),
            (
                "TOPPADDING",
                (0, 0), (-1, -1),
                6,
            ),
            (
                "BOTTOMPADDING",
                (0, 0), (-1, -1),
                6,
            ),
        ])
    )

    story.extend([
        filter_table,
        Spacer(1, 12),
        Paragraph(
            escape(data["report_title"]).upper(),
            styles["Heading2"],
        ),
    ])

    table_data = [
        [
            Paragraph(
                escape(str(value)),
                styles["FleetCell"],
            )
            for value in headers
        ]
    ]

    for row in rows:

        table_data.append([
            Paragraph(
                escape(str(value if value is not None else "—")),
                styles["FleetCell"],
            )
            for value in row
        ])

    available_width = page_size[0] - 20 * mm

    report_table = Table(
        table_data,
        repeatRows=1,
        hAlign="LEFT",
    )

    report_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0), (-1, 0),
                colors.HexColor("#145A40"),
            ),
            (
                "TEXTCOLOR",
                (0, 0), (-1, 0),
                colors.white,
            ),
            (
                "GRID",
                (0, 0), (-1, -1),
                0.35,
                colors.HexColor("#DDE5E0"),
            ),
            (
                "ROWBACKGROUNDS",
                (0, 1), (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#F2F7F4"),
                ],
            ),
            (
                "VALIGN",
                (0, 0), (-1, -1),
                "MIDDLE",
            ),
            (
                "FONTSIZE",
                (0, 0), (-1, -1),
                7,
            ),
            (
                "TOPPADDING",
                (0, 0), (-1, -1),
                6,
            ),
            (
                "BOTTOMPADDING",
                (0, 0), (-1, -1),
                6,
            ),
        ])
    )

    story.append(report_table)

    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            f"Total records: {len(rows)}",
            styles["Normal"],
        )
    )

    def add_page_number(canvas, doc):

        canvas.saveState()

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(
            colors.HexColor("#718096")
        )

        canvas.drawString(
            10 * mm,
            8 * mm,
            "Fleet Insights | Confidential Report",
        )

        canvas.drawRightString(
            doc.pagesize[0] - 10 * mm,
            8 * mm,
            f"Page {doc.page}",
        )

        canvas.restoreState()

    document.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/pdf",
    )

    filename = (
        f"fleet_{data['report_type']}_"
        f"{data['today'].strftime('%Y%m%d')}.pdf"
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )

    return response
