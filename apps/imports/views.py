
# File: apps/imports/views.py

import csv
import io
from datetime import date, datetime
from decimal import Decimal

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date

from openpyxl import load_workbook

from apps.companies.models import Company
from apps.vehicles.models import Vehicle
from apps.drivers.models import Driver
from apps.access_cards.models import AccessCard


# ============================================================
# 1. DATASET CONFIGURATION
# ============================================================

DATASETS = {
    "trucks": {
        "label": "Truck Register",
        "fields": ["company", "reg_no", "make", "model"],
        "required": ["company", "reg_no", "make", "model"],
        "unique_field": "reg_no",
    },

    "people": {
        "label": "People & RFID Access",
        "fields": [
            "name",
            "mobile",
            "organization",
            "occupation",
            "identifier",
            "date_from",
            "date_until",
        ],
        # RFID information is optional.
        # Name and organization are the required driver fields.
        "required": ["name", "organization"],
        "unique_field": None,
    },
}


FIELD_LABELS = {
    "company": "Company",
    "reg_no": "Registration Number",
    "make": "Make",
    "model": "Model",
    "name": "Driver Name",
    "mobile": "Mobile Number",
    "organization": "Organization",
    "occupation": "Occupation",
    "identifier": "RFID Identifier",
    "date_from": "Date From",
    "date_until": "Date Until",
}


# ============================================================
# 2. COLUMN ALIASES
# ============================================================

# All headings are normalized before matching.

ALIASES = {
    # Company / organization
    "company": "company",
    "company name": "company",
    "organization": "organization",
    "organisation": "organization",
    "organization name": "organization",
    "organisation name": "organization",

    # Truck registration
    "reg no": "reg_no",
    "reg number": "reg_no",
    "reg no.": "reg_no",
    "reg.no": "reg_no",
    "registration": "reg_no",
    "registration no": "reg_no",
    "registration no.": "reg_no",
    "registration number": "reg_no",
    "vehicle registration": "reg_no",
    "vehicle registration number": "reg_no",

    # Truck details
    "make": "make",
    "manufacturer": "make",
    "model": "model",
    "vehicle model": "model",

    # Driver details
    "name": "name",
    "driver": "name",
    "driver name": "name",
    "full name": "name",
    "employee name": "name",

    # Mobile
    "mobile nr": "mobile",
    "mobile number": "mobile",
    "mobile no": "mobile",
    "mobile": "mobile",
    "mobile phone": "mobile",
    "phone": "mobile",
    "phone number": "mobile",
    "telephone": "mobile",
    "contact": "mobile",

    # Occupation
    "occupation": "occupation",
    "designation": "occupation",
    "role": "occupation",

    # RFID
    "identifier": "identifier",
    "rfid": "identifier",
    "rfid identifier": "identifier",
    "rfid number": "identifier",
    "card number": "identifier",
    "card id": "identifier",
    "card identifier": "identifier",
    "access card": "identifier",
    "access card number": "identifier",

    # RFID validity dates
    "date from": "date_from",
    "start date": "date_from",
    "valid from": "date_from",
    "effective date": "date_from",

    "date until": "date_until",
    "end date": "date_until",
    "valid until": "date_until",
    "expiry date": "date_until",
    "expiration date": "date_until",
}


# ============================================================
# 3. GENERAL HELPERS
# ============================================================

MAX_UPLOAD_SIZE = 15 * 1024 * 1024
MAX_PREVIEW_ROWS = 3000


def norm(value):
    """Normalize spreadsheet headings for alias matching."""

    return " ".join(
        str(value or "")
        .strip()
        .lower()
        .replace("_", " ")
        .replace("\n", " ")
        .replace("\r", " ")
        .split()
    )


def clean_value(value):
    """Convert spreadsheet values into session-safe strings."""

    if value is None:
        return ""

    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Decimal):
        return format(value, "f")

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value).strip()


def as_date(value):
    """
    Normalize supported date formats.

    Invalid non-empty values are retained so validation
    can flag them instead of silently treating them as blank.
    """

    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    raw = clean_value(value)

    if not raw:
        return ""

    parsed = parse_date(raw)

    if parsed:
        return parsed.isoformat()

    formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue

    return raw


def get_field_from_heading(heading):
    """Convert a spreadsheet heading into an internal field."""

    return ALIASES.get(norm(heading))


def is_empty_row(values):
    """Return True if a spreadsheet row has no meaningful values."""

    return not any(clean_value(value) for value in values)


# ============================================================
# 4. SPREADSHEET READING
# ============================================================

def read_csv_rows(upload):
    """Read CSV records while retaining their original row numbers."""

    try:
        content = upload.read()

        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            decoded = content.decode("cp1252")

        sample = decoded[:8192]

        try:
            dialect = csv.Sniffer().sniff(
                sample,
                delimiters=",;\t|",
            )
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(
            io.StringIO(decoded),
            dialect=dialect,
        )

        if not reader.fieldnames:
            raise ValueError("The CSV file has no column headings.")

        result = []

        for row_number, row in enumerate(reader, start=2):
            cleaned_row = {
                str(key or "").strip(): value
                for key, value in row.items()
                if key is not None
            }

            if is_empty_row(cleaned_row.values()):
                continue

            result.append({
                "sheet": "CSV",
                "line": row_number,
                "raw": cleaned_row,
            })

        return result

    finally:
        upload.seek(0)


def read_excel_rows(upload):
    """
    Read worksheets containing recognized import headings.

    Worksheets such as Read Me, Notes and Instructions are ignored.
    Original worksheet names and Excel row numbers are retained.
    """

    try:
        workbook = load_workbook(
            upload,
            read_only=True,
            data_only=True,
        )
    except Exception as exc:
        raise ValueError(
            f"Unable to open the Excel workbook: {exc}"
        ) from exc

    result = []

    try:
        for worksheet in workbook.worksheets:

            iterator = worksheet.iter_rows(values_only=True)
            headings = next(iterator, None)

            if not headings or is_empty_row(headings):
                continue

            headers = [
                clean_value(value)
                for value in headings
            ]

            recognized_fields = {
                get_field_from_heading(header)
                for header in headers
                if header
            }

            recognized_fields.discard(None)

            # Ignore unrelated worksheets.
            if not recognized_fields:
                continue

            for row_number, values in enumerate(iterator, start=2):

                if is_empty_row(values):
                    continue

                raw = {}

                for index, heading in enumerate(headers):
                    if heading:
                        raw[heading] = (
                            values[index]
                            if index < len(values)
                            else None
                        )

                if is_empty_row(raw.values()):
                    continue

                result.append({
                    "sheet": worksheet.title,
                    "line": row_number,
                    "raw": raw,
                })

    finally:
        workbook.close()
        upload.seek(0)

    return result


def read_rows(upload):
    """Select the appropriate spreadsheet reader."""

    filename = upload.name.lower()

    if filename.endswith(".csv"):
        return read_csv_rows(upload)

    if filename.endswith((".xlsx", ".xlsm")):
        return read_excel_rows(upload)

    raise ValueError(
        "Unsupported file format. Upload a CSV, XLSX or XLSM file."
    )


# ============================================================
# 5. COLUMN NORMALIZATION
# ============================================================

def normalize_record(raw, dataset):
    """Convert a spreadsheet row into the application's field structure."""

    mapped = {}

    for heading, value in raw.items():
        field = get_field_from_heading(heading)

        if field:
            mapped[field] = clean_value(value)

    fields = DATASETS[dataset]["fields"]

    item = {
        field: mapped.get(field, "")
        for field in fields
    }

    if dataset == "trucks":

        item["reg_no"] = (
            item["reg_no"]
            .strip()
            .upper()
            .replace(" ", "")
        )

    elif dataset == "people":

        item["name"] = item["name"].strip()
        item["mobile"] = item["mobile"].strip()
        item["organization"] = item["organization"].strip()
        item["occupation"] = item["occupation"].strip()
        item["identifier"] = item["identifier"].strip()

        item["date_from"] = as_date(item["date_from"])
        item["date_until"] = as_date(item["date_until"])

    return item


def get_missing_columns(source_rows, dataset):
    """
    Identify missing required columns.

    Optional People fields, including RFID details, are not
    reported as missing spreadsheet columns.
    """

    recognized = set()

    for source in source_rows:
        for heading in source["raw"].keys():
            field = get_field_from_heading(heading)

            if field:
                recognized.add(field)

    return [
        field
        for field in DATASETS[dataset]["required"]
        if field not in recognized
    ]


# ============================================================
# 6. DATA VALIDATION
# ============================================================

def validate_record(item, dataset):
    """
    Validate one normalized record.

    People:
      - Name and organization are required.
      - Mobile and occupation are optional.
      - RFID identifier is optional.
      - If RFID identifier exists, both validity dates are required.
      - Validity dates without an RFID identifier are invalid.
    """

    missing = []
    invalid = []

    configuration = DATASETS[dataset]

    for field in configuration["required"]:
        if not str(item.get(field, "")).strip():
            missing.append(field)

    if dataset == "trucks":

        registration = item.get("reg_no", "")

        if registration and len(registration) < 4:
            invalid.append("reg_no")

    elif dataset == "people":

        identifier = item.get("identifier", "").strip()
        start = item.get("date_from", "").strip()
        end = item.get("date_until", "").strip()

        if identifier:
            if not start:
                missing.append("date_from")

            if not end:
                missing.append("date_until")

        elif start or end:
            invalid.append("identifier")

        start_date = parse_date(start) if start else None
        end_date = parse_date(end) if end else None

        if start and not start_date:
            invalid.append("date_from")

        if end and not end_date:
            invalid.append("date_until")

        if start_date and end_date and end_date < start_date:
            invalid.append("date_until")

    return list(dict.fromkeys(missing)), list(dict.fromkeys(invalid))


# ============================================================
# 7. DUPLICATE DETECTION
# ============================================================

def get_existing_identifiers(dataset):
    """
    Retrieve existing identifiers from the database.

    People duplicate checks include:
      - Driver mobile numbers
      - RFID card identifiers
    """

    if dataset == "trucks":

        values = Vehicle.objects.values_list(
            "registration_number",
            flat=True,
        )

        return {
            "reg_no": {
                str(value).strip().upper().replace(" ", "")
                for value in values
                if value
            }
        }

    mobile_values = Driver.objects.values_list(
        "mobile_number",
        flat=True,
    )

    card_values = AccessCard.objects.values_list(
        "identifier",
        flat=True,
    )

    return {
        "mobile": {
            str(value).strip()
            for value in mobile_values
            if value
        },
        "identifier": {
            str(value).strip()
            for value in card_values
            if value
        },
    }


def analyse_rows(dataset, rows):
    """
    Validate rows and detect duplicates in the database
    and within the uploaded spreadsheet.
    """

    existing = get_existing_identifiers(dataset)

    seen_in_file = {
        "reg_no": set(),
        "mobile": set(),
        "identifier": set(),
    }

    for row in rows:

        item = row["data"]

        missing, invalid = validate_record(item, dataset)

        if dataset == "trucks":

            checks = {
                "reg_no": (
                    item.get("reg_no", "")
                    .strip()
                    .upper()
                    .replace(" ", "")
                )
            }

        else:

            checks = {
                "mobile": item.get("mobile", "").strip(),
                "identifier": item.get("identifier", "").strip(),
            }

        duplicate_fields = []
        duplicate_types = []

        for field, key in checks.items():

            if not key:
                continue

            if key in existing.get(field, set()):
                duplicate_fields.append(field)
                duplicate_types.append("existing")

            elif key in seen_in_file[field]:
                duplicate_fields.append(field)
                duplicate_types.append("file")

            seen_in_file[field].add(key)

        if "existing" in duplicate_types:
            duplicate_type = "existing"
        elif "file" in duplicate_types:
            duplicate_type = "file"
        else:
            duplicate_type = ""

        row["missing"] = missing
        row["invalid"] = invalid
        row["duplicate_type"] = duplicate_type
        row["duplicate_fields"] = duplicate_fields
        row["duplicate"] = bool(duplicate_fields)

        row["status"] = (
            "issue"
            if missing or invalid or duplicate_fields
            else "valid"
        )

    return rows


# ============================================================
# 8. PREVIEW SUMMARY
# ============================================================

def build_preview(dataset, rows, filename, missing_columns=None):
    """Build the context required by the import preview template."""

    missing_columns = missing_columns or []

    for row in rows:

        row["cells"] = []

        for field in DATASETS[dataset]["fields"]:

            row["cells"].append({
                "field": field,
                "label": FIELD_LABELS[field],
                "value": row["data"].get(field, ""),
                "missing": field in row.get("missing", []),
                "invalid": field in row.get("invalid", []),
                "duplicate": field in row.get("duplicate_fields", []),
            })

    valid_count = sum(
        row["status"] == "valid"
        for row in rows
    )

    missing_count = sum(
        bool(row["missing"])
        for row in rows
    )

    invalid_count = sum(
        bool(row["invalid"])
        for row in rows
    )

    duplicate_count = sum(
        bool(row["duplicate"])
        for row in rows
    )

    issue_count = sum(
        row["status"] != "valid"
        for row in rows
    )

    return {
        "dataset": dataset,
        "dataset_label": DATASETS[dataset]["label"],
        "filename": filename,

        "fields": DATASETS[dataset]["fields"],

        "headers": [
            FIELD_LABELS[field]
            for field in DATASETS[dataset]["fields"]
        ],

        "field_labels": FIELD_LABELS,
        "rows": rows,

        "total_count": len(rows),
        "valid_count": valid_count,
        "missing_count": missing_count,
        "invalid_count": invalid_count,
        "duplicate_count": duplicate_count,
        "issue_count": issue_count,

        "missing_columns": missing_columns,
        "ready": valid_count > 0,
    }


# ============================================================
# 9. IMPORT UPLOAD AND PREVIEW
# ============================================================

def import_upload(request):
    """
    Upload a spreadsheet, analyse it and display the preview.

    GET:
        Reopen the current preview from the session.

    POST:
        Read and analyse a new CSV or Excel file.
    """

    preview = None

    if request.method == "POST":

        dataset = request.POST.get("dataset", "").strip()
        upload = request.FILES.get("file")

        if dataset not in DATASETS:

            messages.error(
                request,
                "Please select a valid dataset."
            )

        elif not upload:

            messages.error(
                request,
                "Please select a spreadsheet file."
            )

        elif upload.size > MAX_UPLOAD_SIZE:

            messages.error(
                request,
                "The maximum permitted upload size is 15 MB."
            )

        else:

            try:

                source_rows = read_rows(upload)

                if not source_rows:
                    raise ValueError(
                        "No data records were found in the uploaded file. "
                        "Check that the workbook contains a worksheet "
                        "with recognized column headings."
                    )

                if len(source_rows) > MAX_PREVIEW_ROWS:
                    raise ValueError(
                        f"The file contains more than "
                        f"{MAX_PREVIEW_ROWS} data rows. "
                        "Please split it into smaller files."
                    )

                missing_columns = get_missing_columns(
                    source_rows,
                    dataset,
                )

                recognized_fields = (
                    set(DATASETS[dataset]["fields"])
                    - set(missing_columns)
                )

                if not recognized_fields:
                    raise ValueError(
                        "None of the spreadsheet headings could be "
                        "recognized for the selected dataset. "
                        "Check the selected dataset and column headings."
                    )

                rows = []

                for source in source_rows:

                    item = normalize_record(
                        source["raw"],
                        dataset,
                    )

                    rows.append({
                        "line": source["line"],
                        "sheet": source["sheet"],
                        "data": item,
                    })

                rows = analyse_rows(dataset, rows)

                payload = {
                    "dataset": dataset,
                    "filename": upload.name,
                    "rows": rows,
                    "missing_columns": missing_columns,
                }

                request.session["fleet_import"] = payload
                request.session.modified = True

                preview = build_preview(
                    dataset,
                    rows,
                    upload.name,
                    missing_columns,
                )

                messages.success(
                    request,
                    f"{len(rows)} records were analysed successfully."
                )

            except Exception as exc:

                messages.error(
                    request,
                    f"Unable to process the uploaded file: {exc}"
                )

    else:

        # Reopen the previously uploaded preview.
        payload = request.session.get("fleet_import")

        if payload:

            dataset = payload.get("dataset")

            if dataset in DATASETS:

                rows = analyse_rows(
                    dataset,
                    payload.get("rows", []),
                )

                payload["rows"] = rows

                request.session["fleet_import"] = payload
                request.session.modified = True

                preview = build_preview(
                    dataset,
                    rows,
                    payload.get("filename", ""),
                    payload.get("missing_columns", []),
                )

    return render(
        request,
        "imports/upload.html",
        {
            "datasets": DATASETS,
            "preview": preview,
            "selected_dataset": (
                preview["dataset"] if preview else ""
            ),
        },
    )


# ============================================================
# 10. EDIT AND SAVE PREVIEW
# ============================================================

def update_preview(request):
    """Save corrections made to individual preview records."""

    if request.method != "POST":
        return redirect("data_import")

    payload = request.session.get("fleet_import")

    if not payload:
        messages.error(
            request,
            "Your import preview has expired. Please upload the file again."
        )
        return redirect("data_import")

    dataset = payload.get("dataset")

    if dataset not in DATASETS:
        messages.error(
            request,
            "The selected dataset is invalid."
        )
        return redirect("data_import")

    rows = payload.get("rows", [])
    fields = DATASETS[dataset]["fields"]

    for index, row in enumerate(rows):

        for field in fields:

            input_name = f"row_{index}_{field}"

            if input_name not in request.POST:
                continue

            value = request.POST.get(input_name, "").strip()

            if field == "reg_no":
                value = value.upper().replace(" ", "")

            if field in ("date_from", "date_until"):
                value = as_date(value)

            row["data"][field] = value

    rows = analyse_rows(dataset, rows)

    payload["rows"] = rows

    request.session["fleet_import"] = payload
    request.session.modified = True

    messages.success(
        request,
        "Your corrections have been saved. "
        "The records have been validated again."
    )

    return redirect("data_import")


# ============================================================
# 11. CONFIRM AND PROCESS IMPORT
# ============================================================

def import_confirm(request):
    """
    Import valid records inside one database transaction.

    Invalid, missing and duplicate records are skipped.

    People:
      - Create or reuse the organization.
      - Create or reuse the driver when a mobile number exists.
      - Create a new driver when no mobile number is supplied.
      - Create an RFID card only when an identifier is supplied.
    """

    if request.method != "POST":
        return redirect("data_import")

    payload = request.session.get("fleet_import")

    if not payload:
        messages.error(
            request,
            "No import preview was found. Please upload your file again."
        )
        return redirect("data_import")

    dataset = payload.get("dataset")

    if dataset not in DATASETS:
        messages.error(
            request,
            "The import dataset is invalid."
        )
        return redirect("data_import")

    # Revalidate at confirmation time to avoid relying on stale preview data.
    rows = analyse_rows(
        dataset,
        payload.get("rows", []),
    )

    valid_rows = [
        row for row in rows
        if row["status"] == "valid"
    ]

    skipped = len(rows) - len(valid_rows)

    if not valid_rows:
        messages.warning(
            request,
            "There are no valid records to import. "
            "Please correct the outstanding issues."
        )
        return redirect("data_import")

    trucks_created = 0
    drivers_created = 0
    drivers_reused = 0
    cards_created = 0

    try:

        with transaction.atomic():

            for row in valid_rows:

                data = row["data"]

                if dataset == "trucks":

                    company, _ = Company.objects.get_or_create(
                        name=data["company"].strip()
                    )

                    Vehicle.objects.create(
                        company=company,
                        registration_number=data["reg_no"],
                        make=data["make"],
                        model=data["model"],
                    )

                    trucks_created += 1

                elif dataset == "people":

                    organization, _ = Company.objects.get_or_create(
                        name=data["organization"].strip()
                    )

                    mobile = data["mobile"].strip()

                    if mobile:

                        driver, driver_created = Driver.objects.get_or_create(
                            mobile_number=mobile,
                            defaults={
                                "name": data["name"].strip(),
                                "organization": organization,
                                "occupation": (
                                    data["occupation"] or "Driver"
                                ),
                            },
                        )

                        if driver_created:
                            drivers_created += 1
                        else:
                            drivers_reused += 1

                    else:

                        driver = Driver.objects.create(
                            name=data["name"].strip(),
                            mobile_number="",
                            organization=organization,
                            occupation=data["occupation"] or "Driver",
                        )

                        drivers_created += 1

                    # RFID card creation is optional.
                    if data["identifier"].strip():

                        AccessCard.objects.create(
                            driver=driver,
                            identifier=data["identifier"].strip(),
                            date_from=parse_date(data["date_from"]),
                            date_until=parse_date(data["date_until"]),
                        )

                        cards_created += 1

    except IntegrityError:

        messages.error(
            request,
            "A database integrity conflict occurred. "
            "The entire import transaction was rolled back. "
            "Please review the records and try again."
        )

        return redirect("data_import")

    except Exception as exc:

        messages.error(
            request,
            f"The import failed and was rolled back: {exc}"
        )

        return redirect("data_import")

    # Clear the preview only after a successful transaction.
    request.session.pop("fleet_import", None)

    if dataset == "trucks":

        summary = (
            f"{trucks_created} trucks added; "
            f"{skipped} records skipped."
        )

    else:

        summary = (
            f"{drivers_created} new drivers created; "
            f"{drivers_reused} existing drivers reused; "
            f"{cards_created} RFID cards created; "
            f"{skipped} records skipped."
        )

    messages.success(
        request,
        f"Import completed successfully. {summary}"
    )

    return redirect("data_import")
