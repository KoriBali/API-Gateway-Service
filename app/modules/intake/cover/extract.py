"""Membaca file cover YS (PDF atau Excel form) menjadi draf isian request.

Fungsi di sini sinkron dan berat di CPU; router memanggilnya lewat threadpool.
"""
from dataclasses import dataclass
from datetime import date

from loguru import logger

from app.database.models.intake import CoverSourceKind
from app.modules.intake.cover import excel_form, pdf_form

PDF_MAGIC = b"%PDF-"
XLS_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # berkas OLE2, format .xls lama
TEMPLATES = ("ys_pole", "sumi_pole")

CORE_FIELDS = (
    "request_no", "pj_no", "request_type", "design_type", "request_classification",
    "subject", "request_date", "due_date", "requesting_department_name", "notes",
)
SHARED_TEXT_FIELDS = ("scheduled_delivery_date", "requester_pic_name", "drawing_type", "paper_size", "cad_format")
YS_TEXT_FIELDS = (
    "receipt_no", "material_text", "foundation_type", "design_standard_text",
    "wind_speed_text", "opening_height", "concrete_strength", "opening_direction_note",
)
YS_NUMBER_FIELDS = ("foundation_width_x", "foundation_width_y", "embedment_depth")
RAW_FIELDS = {
    "raw_request_type": "requestType", "raw_calc_mark": "calcMark",
    "raw_drawing_mark": "drawingMark", "raw_request_classification": "requestClassification",
    "raw_drawing_type": "drawingType", "raw_paper_size": "paperSize",
    "raw_drawing_data": "drawingData", "raw_foundation_type": "foundationType",
    "raw_foundation_dims": "foundationDims",
}

# Warning hanya untuk isian wajib request. Isian opsional yang tidak terbaca cukup kosong
# di draf; teks aslinya tetap ada di raw.
WARNING_FIELDS = {
    "missing_request_no": "requestNo",
    "missing_pj_no": "pjNo",
    "missing_request_type": "requestType",
    "missing_request_classification": "requestClassification",
    "missing_requesting_department_name": "requestingDepartmentName",
    "missing_subject": "subject",
    "missing_request_date": "requestDate",
    "missing_due_date": "dueDate",
    "design_mark_unreadable": "designType",
    "design_both_x": "designType",
    "classification_multi": "requestClassification",
    "pj_no_ne_sheet_name": "pjNo",
    "due_before_request_date": "dueDate",
}


class CoverUnreadable(Exception):
    """File bukan cover YS yang bisa dibaca. reason dipakai sebagai kode di respons 422."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass
class CoverExtraction:
    source: dict
    draft: dict
    raw: dict
    warnings: list[dict]
    flags: list[str]


def detect_kind(data: bytes) -> CoverSourceKind | None:
    """Jenis file dari byte awalnya, bukan dari nama atau content type kiriman client."""
    if PDF_MAGIC in data[:1024]:
        return CoverSourceKind.pdf
    if data.startswith(XLS_MAGIC):
        return CoverSourceKind.excel
    return None


def extract_cover(data: bytes, kind: CoverSourceKind) -> CoverExtraction:
    try:
        if kind == CoverSourceKind.pdf:
            source, rec, flags = _read_pdf(data)
        else:
            source, rec, flags = _read_excel(data)
    except CoverUnreadable:
        raise
    except Exception as exc:
        # Pustaka PDF dan Excel melempar banyak jenis error untuk file rusak atau terenkripsi.
        logger.warning(f"Cover could not be read ({kind.value}): {exc!r}")
        raise CoverUnreadable("cover_unreadable", "The file could not be read") from exc

    # Tanggal yang tidak ada di kalender (mis. 2026/02/30) diperlakukan sebagai kosong.
    for f in ("request_date", "due_date"):
        if rec[f] and not _is_date(rec[f]):
            rec[f] = ""
            flags.append(f"missing_{f}")
    if rec["request_date"] and rec["due_date"] and rec["due_date"] < rec["request_date"]:
        flags.append("due_before_request_date")
    return CoverExtraction(
        source=source,
        draft=_draft(rec),
        raw={key: rec[col] for col, key in RAW_FIELDS.items() if rec.get(col)},
        warnings=[{"code": f, "field": WARNING_FIELDS[f]} for f in flags if f in WARNING_FIELDS],
        flags=flags,
    )


def _read_pdf(data: bytes):
    page, words, template = pdf_form.find_form_page(data)
    if page is None or template not in TEMPLATES:
        raise CoverUnreadable("cover_not_recognized", "The file is not a YS request form")
    rec, flags = pdf_form.extract_fields(words)
    return {"kind": "pdf", "template": template, "page": page, "sheet": None}, rec, flags


def _read_excel(data: bytes):
    book = excel_form.open_book(data)
    kinds = [(sheet, excel_form.detect_kind(sheet, book)) for sheet in book.sheets()]
    sheet = next((s for s, k in kinds if k == "form"), None)
    if sheet is None:
        if any(k == "list" for _, k in kinds):
            raise CoverUnreadable(
                "cover_list_not_supported",
                "An Excel request list is not supported; upload the request form of one request",
            )
        raise CoverUnreadable("cover_not_recognized", "The file is not a YS request form")
    template, rec, flags = excel_form.extract_form(sheet, book)
    if template not in TEMPLATES:
        raise CoverUnreadable("cover_not_recognized", "The file is not a YS request form")
    return {"kind": "excel", "template": template, "page": None, "sheet": sheet.name}, rec, flags


def _is_date(text: str) -> bool:
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _draft(rec: dict) -> dict:
    """Record teks -> draf bertipe (nama field snake_case). Teks kosong menjadi None."""
    draft = {f: rec.get(f) or None for f in CORE_FIELDS}
    draft["brand_line"] = "ys"
    for f in ("request_date", "due_date"):
        draft[f] = date.fromisoformat(draft[f]) if draft[f] else None

    shared = {f: rec.get(f) or None for f in SHARED_TEXT_FIELDS}
    shared["delivery_quantity"] = int(rec["delivery_quantity"]) if rec.get("delivery_quantity") else None
    shared["is_cad_data_requested"] = {"true": True, "false": False}.get(rec.get("is_cad_data_requested", ""))

    ys = {f: rec.get(f) or None for f in YS_TEXT_FIELDS}
    for f in YS_NUMBER_FIELDS:
        ys[f] = float(rec[f]) if rec.get(f) else None

    draft["shared_details"] = shared
    draft["ys_details"] = ys
    return draft
