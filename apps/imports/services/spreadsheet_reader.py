
# File: apps/imports/services/spreadsheet_reader.py

import csv
import io
import re

from pathlib import Path

from openpyxl import load_workbook


class SpreadsheetReadError(Exception):
    """Raised when an uploaded spreadsheet cannot be read."""


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xlsm"}


def normalize_header(value):
    """
    Convert a spreadsheet header into a consistent comparison format.
    """

    if value is None:
        return ""

    value = str(value).strip().lower()

    value = re.sub(r"[\n\r\t]+", " ", value)
    value = re.sub(r"[^a-z0-9]+", "_", value)

    return value.strip("_")


def clean_cell(value):
    """
    Normalize spreadsheet cell values without changing their meaning.
    """

    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    return value


def is_empty_row(values):
    """
    Check whether a row contains any meaningful values.
    """

    return not any(
        value is not None and str(value).strip() != ""
        for value in values
    )


def trim_empty_columns(rows):
    """
    Remove columns that are completely empty across all rows.
    """

    if not rows:
        return []

    maximum_columns = max(len(row) for row in rows)

    last_used_column = -1

    for column_index in range(maximum_columns):
        if any(
            column_index < len(row)
            and row[column_index] is not None
            and str(row[column_index]).strip() != ""
            for row in rows
        ):
            last_used_column = column_index

    if last_used_column == -1:
        return []

    return [
        list(row[:last_used_column + 1])
        for row in rows
    ]


def detect_header_row(rows, scan_limit=15):
    """
    Detect the most likely header row.

    The reader scans the first non-empty rows and gives preference
    to rows containing several distinct text values.

    Returns the zero-based row index.
    """

    best_index = None
    best_score = -1

    for index, row in enumerate(rows[:scan_limit]):
        if is_empty_row(row):
            continue

        values = [
            str(value).strip()
            for value in row
            if value is not None and str(value).strip()
        ]

        if not values:
            continue

        text_count = sum(
            1 for value in values
            if not re.fullmatch(r"[-+]?\d+(\.\d+)?", value)
        )

        unique_count = len({
            normalize_header(value)
            for value in values
            if normalize_header(value)
        })

        score = (
            text_count * 2
            + unique_count
            + min(len(values), 10)
        )

        if score > best_score:
            best_score = score
            best_index = index

    return best_index


def make_unique_headers(header_values):
    """
    Ensure that every column has a usable and unique header.
    """

    headers = []
    used = {}

    for index, value in enumerate(header_values, start=1):
        header = str(value).strip() if value is not None else ""

        if not header:
            header = f"column_{index}"

        base_header = header
        count = used.get(base_header.lower(), 0) + 1
        used[base_header.lower()] = count

        if count > 1:
            header = f"{base_header}_{count}"

        headers.append(header)

    return headers


def rows_to_records(raw_rows, sheet_name):
    """
    Convert worksheet rows into a consistent collection of records.

    Each record contains:
        sheet_name
        row_number
        data
    """

    raw_rows = trim_empty_columns(raw_rows)

    if not raw_rows:
        return {
            "sheet_name": sheet_name,
            "headers": [],
            "rows": [],
            "header_row": None,
        }

    header_index = detect_header_row(raw_rows)

    if header_index is None:
        return {
            "sheet_name": sheet_name,
            "headers": [],
            "rows": [],
            "header_row": None,
        }

    headers = make_unique_headers(raw_rows[header_index])

    records = []

    for index in range(header_index + 1, len(raw_rows)):
        values = raw_rows[index]

        if is_empty_row(values):
            continue

        values = list(values[:len(headers)])

        if len(values) < len(headers):
            values.extend([""] * (len(headers) - len(values)))

        record_data = {
            headers[column_index]: clean_cell(value)
            for column_index, value in enumerate(values)
        }

        records.append({
            "sheet_name": sheet_name,
            "row_number": index + 1,
            "data": record_data,
        })

    return {
        "sheet_name": sheet_name,
        "headers": headers,
        "rows": records,
        "header_row": header_index + 1,
    }


def read_csv_file(uploaded_file):
    """
    Read a CSV file and return a standardized sheet structure.
    """

    try:
        content = uploaded_file.read()

        if isinstance(content, bytes):
            decoded = None

            for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
                try:
                    decoded = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue

            if decoded is None:
                raise SpreadsheetReadError(
                    "The CSV file encoding could not be identified."
                )
        else:
            decoded = content

        sample = decoded[:8192]

        try:
            dialect = csv.Sniffer().sniff(
                sample,
                delimiters=",;\t|",
            )
        except csv.Error:
            dialect = csv.excel

        reader = csv.reader(io.StringIO(decoded), dialect)

        raw_rows = [
            list(row)
            for row in reader
        ]

        sheet = rows_to_records(
            raw_rows,
            sheet_name="CSV",
        )

        return {
            "filename": Path(uploaded_file.name).name,
            "file_type": "csv",
            "sheets": [sheet],
            "total_rows": len(sheet["rows"]),
        }

    except SpreadsheetReadError:
        raise

    except Exception as exc:
        raise SpreadsheetReadError(
            f"Unable to read the CSV file: {exc}"
        ) from exc

    finally:
        uploaded_file.seek(0)


def read_excel_file(uploaded_file):
    """
    Read every worksheet in an Excel workbook.
    """

    workbook = None

    try:
        workbook = load_workbook(
            uploaded_file,
            read_only=True,
            data_only=True,
        )

        sheets = []

        for worksheet in workbook.worksheets:
            raw_rows = [
                list(row)
                for row in worksheet.iter_rows(
                    values_only=True
                )
            ]

            sheet = rows_to_records(
                raw_rows,
                sheet_name=worksheet.title,
            )

            if sheet["rows"]:
                sheets.append(sheet)

        total_rows = sum(
            len(sheet["rows"])
            for sheet in sheets
        )

        return {
            "filename": Path(uploaded_file.name).name,
            "file_type": Path(uploaded_file.name).suffix.lower().lstrip("."),
            "sheets": sheets,
            "total_rows": total_rows,
        }

    except SpreadsheetReadError:
        raise

    except Exception as exc:
        raise SpreadsheetReadError(
            f"Unable to read the Excel workbook: {exc}"
        ) from exc

    finally:
        if workbook is not None:
            workbook.close()

        uploaded_file.seek(0)


def read_spreadsheet(uploaded_file):
    """
    Main entry point for reading supported spreadsheet uploads.

    Returns a dictionary containing:
        filename
        file_type
        sheets
        total_rows
    """

    filename = getattr(uploaded_file, "name", "")

    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise SpreadsheetReadError(
            "Unsupported file format. Upload a CSV, XLSX or XLSM file."
        )

    if extension == ".csv":
        return read_csv_file(uploaded_file)

    return read_excel_file(uploaded_file)
