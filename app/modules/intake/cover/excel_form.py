"""Pembaca request form YS dari export Excel DataBank (.xls), satu sheet = satu request.

Field dicari lewat label di sel; nilainya = sel tidak kosong di kanannya. Export daftar
request (satu baris = satu request) dikenali tetapi tidak dibaca, karena tidak memuat
特記事項 dan sebagian besar field detail.
"""
import io

import xlrd

from app.modules.intake.cover import fields as cf
from app.modules.intake.cover.fields import FORM_LABELS


def open_book(data: bytes):
    # Export DataBank tidak selalu menyimpan codepage; teks Jepangnya Shift-JIS (cp932).
    # logfile dibuang: xlrd mencetak peringatan OLE2 yang tidak berbahaya untuk file ini.
    return xlrd.open_workbook(file_contents=data, encoding_override="cp932", logfile=io.StringIO())


def cell_text(sheet, book, r, c):
    """Nilai sel sebagai teks. Tanggal Excel -> 2026/01/15, angka bulat tanpa .0."""
    cell = sheet.cell(r, c)
    if cell.ctype == xlrd.XL_CELL_DATE:
        return xlrd.xldate_as_datetime(cell.value, book.datemode).strftime("%Y/%m/%d")
    if cell.ctype == xlrd.XL_CELL_NUMBER:
        v = cell.value
        return str(int(v)) if float(v).is_integer() else str(v)
    return str(cell.value).replace("\r\n", "\n").replace("\r", "\n").strip()


def detect_kind(sheet, book):
    """'form' (ada judul 伺書), 'list' (header 依頼No + PJNo), atau None."""
    for r in range(min(sheet.nrows, 10)):
        row = [cell_text(sheet, book, r, c) for c in range(sheet.ncols)]
        if any("伺書" in v for v in row):
            return "form"
        if "依頼No" in row and "PJNo" in row:
            return "list"
    return None


def find_labels(sheet, book, label):
    return [(r, c) for r in range(sheet.nrows) for c in range(sheet.ncols)
            if cell_text(sheet, book, r, c) == label]


def value_right(sheet, book, pos, stop_labels=FORM_LABELS):
    """Gabungan sel tidak kosong di kanan label, sampai sel label form berikutnya."""
    if not pos:
        return ""
    r, c = pos
    parts = []
    for cc in range(c + 1, sheet.ncols):
        v = cell_text(sheet, book, r, cc)
        if v in stop_labels:
            break
        if v:
            parts.append(v)
    return " ".join(parts).strip()


def detail_raw(sheet, book):
    """Teks mentah per label untuk kolom shared dan YS."""
    def first(label):
        return min(find_labels(sheet, book, label), default=None)

    raw = {label: value_right(sheet, book, first(label))
           for label in cf.DETAIL_LABELS if label not in cf.DIM_LABELS}

    # 受付No: nilainya di sel BAWAH label (kolom stempel), bukan di kanan.
    raw["受付No"] = ""
    pos = first("受付No")
    if pos:
        r, c = pos
        raw["受付No"] = next((cell_text(sheet, book, rr, cc)
                             for rr in range(r + 1, min(r + 4, sheet.nrows))
                             for cc in range(c, min(c + 2, sheet.ncols))
                             if cf.RECEIPT_NO_RE.fullmatch(cell_text(sheet, book, rr, cc))), "")

    # 担当 peminta ada di kolom label paling kiri; dua 担当 lain di kolom stempel.
    tanto = find_labels(sheet, book, "担当")
    raw["担当"] = value_right(sheet, book, min(tanto, key=lambda p: (p[1], p[0]), default=None))

    # 基礎寸法: 巾(直径) / 奥行 / 深さ di baris yang sama dengan label 基礎寸法.
    kiso = first("基礎寸法")
    haba = next((p for p in find_labels(sheet, book, "巾(直径)") if kiso and p[0] == kiso[0]), None)
    raw.update(cf.split_dims(value_right(sheet, book, haba)))
    return raw


def extract_form(sheet, book):
    """Satu sheet form -> (template, record, flag). Record memakai nama kolom tabel request."""
    rec, flags = {}, []

    def first(label):
        return min(find_labels(sheet, book, label), default=None)

    def get(label, **kw):
        return value_right(sheet, book, first(label), **kw)

    title = next(cell_text(sheet, book, r, c) for r in range(min(sheet.nrows, 10))
                 for c in range(sheet.ncols) if "伺書" in cell_text(sheet, book, r, c))
    template = cf.template_of(title)

    rec["request_no"] = cf.norm_request_no(get("依頼No"))
    rec["pj_no"] = cf.norm_pj_no(get("PJ.NO"))

    raw_type = get("種別").split("【")[0].strip()  # 種別 paling atas = 一般 / 特殊
    rec["raw_request_type"] = raw_type
    rec["request_type"] = cf.norm_request_type(raw_type)

    # 計算書 / 図面 juga muncul di blok bawah form; dipilih yang nilainya berisi 【.
    def mark_value(label):
        for pos in find_labels(sheet, book, label):
            val = value_right(sheet, book, pos)
            if "【" in val:
                return val
        return ""

    raw_calc, raw_draw = mark_value("計算書"), mark_value("図面")
    rec["raw_calc_mark"], rec["raw_drawing_mark"] = raw_calc, raw_draw
    calc, draw = cf.mark(raw_calc), cf.mark(raw_draw)
    rec["design_type"] = cf.design_type_from_marks(calc, draw)
    if calc is None or draw is None:
        flags.append("design_mark_unreadable")
    elif not calc and not draw:
        flags.append("design_both_x")

    raw_cls = get("区分")
    rec["raw_request_classification"] = raw_cls
    rec["request_classification"], multi = cf.norm_classification(raw_cls)
    if multi:
        flags.append("classification_multi")

    rec["requesting_department_name"] = cf.clean_department(get("会社名"))
    rec["subject"] = get("物件名", stop_labels=set())
    rec["request_date"] = cf.norm_date(get("依頼日"))
    rec["due_date"] = cf.norm_date(get("要望期日"))

    # 特記事項: baris di bawah OUTの計算書 sampai sebelum blok 計算書/図面 (kolom A).
    out_pos = first("OUTの計算書")
    bottom = [r for r, c in find_labels(sheet, book, "計算書") if c == 0]
    if out_pos:
        r_end = min(bottom) if bottom else sheet.nrows
        lines = [cell_text(sheet, book, r, c) for r in range(out_pos[0] + 1, r_end)
                 for c in range(1, sheet.ncols)]
        rec["notes"] = "\n".join(line for line in lines if line)
    else:
        rec["notes"] = ""
        flags.append("notes_block_not_found")

    flags += cf.missing_flags(rec)

    details, detail_flags = cf.build_details(detail_raw(sheet, book), rec["design_type"])
    rec.update(details)
    flags += detail_flags

    # Nama sheet form = {PJ.NO}_{受付No}.
    sheet_pj = sheet.name.split("_")[0]
    if sheet_pj.isdigit() and rec["pj_no"] and sheet_pj != rec["pj_no"]:
        flags.append("pj_no_ne_sheet_name")
    return template, rec, flags
