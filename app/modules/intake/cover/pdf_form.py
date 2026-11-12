"""Pembaca request form YS berbentuk PDF.

Field dicari lewat posisi relatif terhadap label yang tercetak (anchor label), bukan
koordinat tetap, karena template スミポール (ekspor Excel) skalanya berbeda per file.
Kata adalah tuple (x0, top, x1, bottom, text) dengan koordinat dari kiri atas halaman
dalam orientasi baca.
"""
import io

import pdfplumber

from app.modules.intake.cover import fields as cf
from app.modules.intake.cover.fields import FORM_LABELS

# Form tidak selalu di halaman 1 (kadang didahului lampiran), tetapi selalu di awal.
MAX_SCAN_PAGES = 4
NOTES_LABEL_CHARS = {"特", "記", "事", "項"}


def page_words(page):
    """Kata + bbox satu halaman. Anotasi yang ditempel di atas form tidak ikut terbaca,
    karena pdfplumber hanya membaca content stream halaman. Koordinat pdfplumber ada di
    ruang halaman yang belum diputar, jadi halaman ber-/Rotate diputar ke orientasi baca."""
    width, height = float(page.width), float(page.height)
    rotate = int(page.rotation or 0) % 360
    words = []
    for w in page.extract_words(keep_blank_chars=False):
        x0, y0, x1, y1 = float(w["x0"]), float(w["top"]), float(w["x1"]), float(w["bottom"])
        if rotate == 90:
            x0, y0, x1, y1 = y0, width - x1, y1, width - x0
        elif rotate == 270:
            x0, y0, x1, y1 = height - y1, x0, height - y0, x1
        elif rotate == 180:
            x0, y0, x1, y1 = width - x1, height - y1, width - x0, height - y0
        words.append((x0, y0, x1, y1, w["text"]))
    return words


def find_form_page(data: bytes):
    """(nomor halaman, kata, template) halaman pertama yang memuat judul 伺書, atau
    (None, None, None) bila tidak ada di halaman awal."""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for no, page in enumerate(pdf.pages[:MAX_SCAN_PAGES], 1):
            words = page_words(page)
            title = next((w[4] for w in words if "伺書" in w[4]), None)
            if title:
                return no, words, cf.template_of(title)
    return None, None, None


def ycenter(w):
    return (w[1] + w[3]) / 2


def first_label(words, label):
    hits = [w for w in words if w[4] == label]
    return min(hits, key=lambda w: (w[1], w[0])) if hits else None


def value_right_of(words, label_word, stop_labels=FORM_LABELS, x_limit=None):
    """Kata di baris yang sama, di kanan label, sampai label form berikutnya."""
    if label_word is None:
        return ""
    yc, h = ycenter(label_word), label_word[3] - label_word[1]
    row = sorted((w for w in words
                  if w is not label_word and abs(ycenter(w) - yc) < h * 0.6
                  and w[0] >= label_word[2] - 0.5),
                 key=lambda w: w[0])
    limit = min([w[0] for w in row if w[4] in stop_labels] + [x_limit or 1e12])
    return " ".join(w[4] for w in row if w[0] < limit).strip()


def lines_in_box(words, x_min, y_min, y_max):
    """Gabungkan kata dalam kotak menjadi baris teks (atas ke bawah, kiri ke kanan)."""
    box = sorted((w for w in words if w[0] >= x_min and y_min <= ycenter(w) <= y_max
                  and w[4] not in NOTES_LABEL_CHARS), key=lambda w: (ycenter(w), w[0]))
    lines, current, cur_y = [], [], None
    for w in box:
        h = w[3] - w[1]
        if cur_y is not None and abs(ycenter(w) - cur_y) > h * 0.6:
            lines.append(current)
            current = []
        if not current:
            cur_y = ycenter(w)
        current.append(w)
    if current:
        lines.append(current)
    return "\n".join(" ".join(w[4] for w in sorted(line, key=lambda w: w[0])) for line in lines)


def extract_notes(words):
    """特記事項: di bawah baris OUTの計算書, di atas blok 計算書/図面 (処置), di kanan
    kolom label. None bila baris acuannya tidak ada."""
    top_anchor = first_label(words, "OUTの計算書") or first_label(words, "形状寸法変更")
    if not top_anchor:
        return None
    shori = [w for w in words if w[4] == "処置"]
    toku = [w for w in words if w[4] == "特"]
    y_min = top_anchor[3] + 1
    # Batas bawah: awal blok 計算書 (huruf vertikal 計), atau baris 処置 bila tidak ada.
    kei = [w for w in words if w[4] == "計" and w[1] > y_min]
    if kei:
        y_max = min(w[1] for w in kei) - 1
    elif shori:
        y_max = min(w[1] for w in shori) - 1
    else:
        y_max = 1e12
    # Baris instruksi tercetak di bawah OUTの計算書 masih milik blok OUT, bukan catatan.
    printed = [w for w in words if "必ず下記特記事項" in w[4]]
    if printed:
        y_min = max(y_min, max(w[3] for w in printed) + 1)
    x_min = (max(w[2] for w in toku) + 1) if toku else 0
    return lines_in_box(words, x_min, y_min, y_max)


def mark_value(words, label):
    """Nilai 【○/×】 untuk label 計算書 / 図面. Kata yang sama bisa muncul di teks bebas
    (mis. 物件名 berisi 計算書), jadi dipilih kemunculan pertama yang diikuti 【."""
    for lab in sorted((w for w in words if w[4] == label), key=lambda w: (w[1], w[0])):
        val = value_right_of(words, lab)
        if "【" in val:
            return val
    return ""


def receipt_below(words, label_word):
    """受付No: nilainya ada di BAWAH label (kolom stempel), bukan di kanan."""
    if label_word is None:
        return ""
    h = label_word[3] - label_word[1]
    nxt = [w[0] for w in words if w[4] == "受付" and abs(ycenter(w) - ycenter(label_word)) < h]
    x_max = min(nxt) if nxt else label_word[2] + 3 * h
    below = sorted((w for w in words
                    if label_word[3] < w[1] < label_word[3] + 4 * h
                    and label_word[0] - 2 * h <= w[0] < x_max
                    and cf.RECEIPT_NO_RE.fullmatch(w[4])), key=lambda w: w[1])
    return below[0][4] if below else ""


def detail_raw(words):
    """Teks mentah per label untuk kolom shared dan YS."""
    raw = {label: value_right_of(words, first_label(words, label))
           for label in cf.DETAIL_LABELS if label not in cf.DIM_LABELS}

    uketsuke = first_label(words, "受付No")
    raw["受付No"] = receipt_below(words, uketsuke)
    # 担当 ada tiga: dua di kolom stempel kanan atas, satu (peminta) paling kiri.
    # Nilainya dipotong sebelum kolom 受付No, tempat stempel bisa menempel di baris yang sama.
    tanto = [w for w in words if w[4] == "担当"]
    pic = min(tanto, key=lambda w: w[0]) if tanto else None
    raw["担当"] = value_right_of(words, pic, x_limit=uketsuke[0] - 1 if uketsuke else None)

    # 基礎寸法: 巾(直径) / 奥行 / 深さ di satu baris. Sub-label bisa menempel ke nilai
    # (お任せ奥行), jadi baris diambil utuh dari kanan 巾(直径) lalu dipecah split_dims().
    kiso = first_label(words, "基礎寸法")
    haba = None
    if kiso:
        h = kiso[3] - kiso[1]
        haba = next((w for w in words if w[4] == "巾(直径)"
                     and abs(ycenter(w) - ycenter(kiso)) < h), None)
    raw.update(cf.split_dims(value_right_of(words, haba)))
    return raw


def extract_fields(words):
    """Satu halaman form -> (record, flag). Record memakai nama kolom tabel request."""
    rec, flags = {}, []

    def get(label, **kw):
        return value_right_of(words, first_label(words, label), **kw)

    rec["request_no"] = cf.norm_request_no(get("依頼No"))
    rec["pj_no"] = cf.norm_pj_no(get("PJ.NO"))

    # 種別 kiri atas: label 種別 paling atas. Isinya hanya 一般 / 特殊.
    raw_type = get("種別").split("【")[0].strip()
    rec["raw_request_type"] = raw_type
    rec["request_type"] = cf.norm_request_type(raw_type)

    raw_calc, raw_draw = mark_value(words, "計算書"), mark_value(words, "図面")
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

    # 会社名 berhenti sebelum kolom 受付No (berisi nomor penerimaan dan tanggal cap).
    uketsuke = first_label(words, "受付No")
    rec["requesting_department_name"] = cf.clean_department(
        get("会社名", x_limit=uketsuke[0] - 1 if uketsuke else None))

    # Baris 物件名 hanya berisi nilai, jadi kata seperti 計算書 di dalamnya bukan label.
    rec["subject"] = get("物件名", stop_labels=set())
    rec["request_date"] = cf.norm_date(get("依頼日"))
    rec["due_date"] = cf.norm_date(get("要望期日"))

    notes = extract_notes(words)
    rec["notes"] = notes or ""
    if notes is None:
        flags.append("notes_block_not_found")

    flags += cf.missing_flags(rec)

    details, detail_flags = cf.build_details(detail_raw(words), rec["design_type"])
    rec.update(details)
    return rec, flags + detail_flags
