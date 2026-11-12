"""Label form request YS (設計依頼兼発注伺書) dan aturan normalisasi nilainya.

Dipakai pembaca PDF dan pembaca Excel, supaya kedua sumber menghasilkan nilai yang sama.
Semua fungsi menerima dan mengembalikan teks; string kosong berarti tidak terbaca.
"""
import re
import unicodedata

# Label field shared + YS. Teks mentah dikumpulkan per label ini, lalu build_details()
# menormalisasinya.
DETAIL_LABELS = [
    "納入時期", "納入数量", "担当", "図面種類", "用紙指定", "図面データ", "受付No", "材質",
    "基礎形状", "巾(直径)", "奥行", "深さ", "規格", "設計風速(m/s)", "開口部高さ",
    "ｺﾝｸﾘｰﾄ強度", "開口部方向",
]
# Sub-label 基礎寸法, hanya dipakai di baris 基礎寸法.
DIM_LABELS = {"巾(直径)", "奥行", "深さ"}

# Semua label yang tercetak di form. Dipakai sebagai batas kanan nilai sebuah field.
FORM_LABELS = {
    "種別", "依頼No", "依頼日", "会社名", "担当", "受付No", "受付", "室長", "区分", "PJ.NO",
    "要望期日", "入票", "受注確立", "納入時期", "納入数量", "客先仕様", "物件名", "灯具メーカー",
    "計算書", "図面", "提出書類", "図面種類", "用紙指定", "型式", "柱形状", "規格", "設置場所",
    "設計風速(m/s)", "器具形式", "灯具略号", "材質", "表面処理", "断面形状", "塗装種類",
    "開口部高さ", "色調", "開口部方向", "色番号", "地際処理", "アンカー", "貼り紙防止種別",
    "アンカー寸法", "貼り紙防止塗装", "ｺﾝｸﾘｰﾄ強度", "地際部塗装", "開口部計算", "基礎計算",
    "基礎形状", "基礎寸法", "前注品", "図面No", "計算書No", "添付資料", "図面データ",
    "形状寸法変更", "OUTの計算書", "計算結果がOUTの場合", "処置", "作成者",
}

REQUEST_NO_RE = re.compile(r"[A-Z]+-\d{2}-\d+")
DATE_RE = re.compile(r"(\d{4})[/年.-](\d{1,2})[/月.-](\d{1,2})")
# 受付No (26-0035) dan tanggal cap ('26.01.15) yang kadang menempel di nilai 会社名.
STAMP_RE = re.compile(r"^'?\d{2}[-.]\d{2,4}")
RECEIPT_NO_RE = re.compile(r"\d{2}-\d{3,5}")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

# 図面種類 -> drawing_type. Kata yang muncul pertama menang: 承認図(製作図必要) = approval.
DRAWING_TYPE_WORDS = {
    "承認図": "approval", "製作図": "manufacturer", "発注図": "order",
    "打ち合わせ図": "meeting", "打合せ図": "meeting", "打合図": "meeting",
}
NONE_WORDS = {"無し", "なし", "無", "不要"}


def template_of(title: str) -> str:
    if "ＹＳポール" in title:
        return "ys_pole"
    if "スミポール" in title:
        return "sumi_pole"
    return "unknown"


def norm_request_no(raw):
    m = REQUEST_NO_RE.search((raw or "").replace(" ", ""))
    return m.group(0) if m else ""


def norm_pj_no(raw):
    m = re.search(r"\d+", str(raw or ""))
    return m.group(0) if m else ""


def norm_date(raw):
    m = DATE_RE.search(raw or "")
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


def norm_request_type(raw):
    """種別: 一般 -> general, 特殊 -> special."""
    m = re.search(r"一般|特殊", raw or "")
    return {"一般": "general", "特殊": "special"}.get(m.group(0) if m else "", "")


def norm_classification(raw):
    """区分. Bila lebih dari satu (mis. 新規・変更), ambil yang pertama.
    Kembalikan (nilai, lebih_dari_satu)."""
    found = re.findall(r"流用新規|新規|変更", raw or "")
    value = {"新規": "new", "変更": "change", "流用新規": "reuse_new"}.get(found[0] if found else "", "")
    return value, len(found) > 1


def mark(raw):
    """【○】 -> True, 【×】 -> False, lainnya -> None."""
    if "○" in raw or "〇" in raw:
        return True
    if "×" in raw or "✕" in raw:
        return False
    return None


def design_type_from_marks(calc, draw):
    """Dari tanda 計算書 dan 図面 di form."""
    return {(True, True): "drawing_calculation", (True, False): "calculation",
            (False, True): "drawing"}.get((calc, draw), "")


def clean_department(raw):
    """Potong token 受付No / tanggal cap yang menempel di belakang 会社名."""
    tokens = (raw or "").split(" ")
    cut = next((i for i, t in enumerate(tokens) if STAMP_RE.match(t)), len(tokens))
    return " ".join(tokens[:cut]).strip()


def missing_flags(rec, columns=("request_no", "pj_no", "request_type",
                                "request_classification", "requesting_department_name",
                                "subject", "request_date", "due_date")):
    return [f"missing_{c}" for c in columns if not rec.get(c)]


def norm_space(raw):
    """Rapikan spasi, termasuk spasi lebar penuh (影山　莉子 -> 影山 莉子)."""
    return " ".join(str(raw or "").replace("　", " ").split())


def norm_receipt_no(raw):
    m = RECEIPT_NO_RE.search(raw or "")
    return m.group(0) if m else ""


def norm_drawing_type(raw):
    hits = [(raw.find(w), v) for w, v in DRAWING_TYPE_WORDS.items() if w in (raw or "")]
    return min(hits)[1] if hits else ""


def norm_paper_size(raw):
    """用紙指定: 無し -> None (label pilihan di form intake), A1..A4 / isian lain apa adanya."""
    raw = norm_space(raw)
    return "None" if raw in NONE_WORDS else raw


def norm_cad_data(raw):
    """図面データ: '必要 DWG' -> (True, 'DWG'), '不要' -> (False, ''), kosong -> (None, '')."""
    raw = norm_space(raw)
    requested = True if "必要" in raw else False if "不要" in raw else None
    fmt = norm_space(raw.replace("必要", "").replace("不要", ""))
    return requested, fmt


def _number(raw):
    # NFKC: angka lebar penuh (６00) -> ASCII (600).
    text = unicodedata.normalize("NFKC", raw or "").replace(",", "")
    m = NUMBER_RE.search(text)
    return m.group(0) if m else ""


def norm_int(raw):
    n = _number(raw)
    return str(int(float(n))) if n else ""


def split_dims(text):
    """Teks di kanan 巾(直径) -> {巾(直径), 奥行, 深さ}. Teks bisa '500 奥行 500 深さ 1300',
    atau sub-label menempel ke nilai ('お任せ奥行 お任せ深さ お任せ')."""
    parts = re.split(r"(奥行|深さ)", text or "")
    out = {"巾(直径)": parts[0].strip(), "奥行": "", "深さ": ""}
    for label, value in zip(parts[1::2], parts[2::2]):
        out[label] = value.strip()
    return out


def norm_foundation_type(raw):
    """基礎形状: 矩形 / 角 -> square, 円形 / 丸 -> circle."""
    if re.search(r"矩形|角", raw or ""):
        return "square"
    if re.search(r"円|丸", raw or ""):
        return "circle"
    return ""


def norm_concrete(raw):
    """'18 N/mm 2' (PDF, pangkat jadi kata terpisah) dan '18 N/mm2' (Excel) -> '18 N/mm²'."""
    return re.sub(r"N/mm\s*[2²]", "N/mm²", norm_space(raw))


def build_details(raw, design_type=""):
    """Teks mentah per label -> kolom shared + YS, nilai raw_*, dan flag.
    design_type dipakai untuk memeriksa blok 提出書類, yang hanya relevan bila ada gambar."""
    def g(label):
        return norm_space(raw.get(label, ""))

    rec, flags = {}, []

    # 納入時期 adalah teks bebas (2026年度, 3/末), tidak diparse sebagai tanggal.
    rec["scheduled_delivery_date"] = g("納入時期")
    rec["delivery_quantity"] = norm_int(g("納入数量"))
    if g("納入数量") and not rec["delivery_quantity"]:
        flags.append("delivery_quantity_not_number")
    rec["requester_pic_name"] = g("担当")

    rec["raw_drawing_type"] = g("図面種類")
    rec["drawing_type"] = norm_drawing_type(rec["raw_drawing_type"])
    if rec["raw_drawing_type"] and not rec["drawing_type"]:
        flags.append("drawing_type_unmapped")

    rec["raw_paper_size"] = g("用紙指定")
    rec["paper_size"] = norm_paper_size(rec["raw_paper_size"])

    rec["raw_drawing_data"] = g("図面データ")
    requested, fmt = norm_cad_data(rec["raw_drawing_data"])
    rec["is_cad_data_requested"] = "" if requested is None else str(requested).lower()
    rec["cad_format"] = fmt
    if rec["raw_drawing_data"] and requested is None:
        flags.append("cad_data_unreadable")

    has_drawing = "drawing" in design_type
    drawing_block = rec["raw_drawing_type"] or rec["raw_paper_size"] or rec["raw_drawing_data"]
    if design_type and has_drawing and not rec["raw_drawing_type"]:
        flags.append("drawing_type_missing_for_drawing")
    if design_type and not has_drawing and drawing_block:
        flags.append("drawing_block_on_calc_only")

    rec["receipt_no"] = norm_receipt_no(g("受付No"))
    rec["material_text"] = g("材質")

    rec["raw_foundation_type"] = g("基礎形状")
    rec["foundation_type"] = norm_foundation_type(rec["raw_foundation_type"])
    if rec["raw_foundation_type"] and not rec["foundation_type"]:
        flags.append("foundation_type_unmapped")
    dims = (("巾(直径)", "foundation_width_x"), ("奥行", "foundation_width_y"),
            ("深さ", "embedment_depth"))
    # Isian non-angka (X, お任せ, 別紙) tidak muat di kolom angka; teks aslinya disimpan.
    if any(g(label) for label, _ in dims):
        rec["raw_foundation_dims"] = " | ".join(f"{label}={g(label)}" for label, _ in dims)
    for label, col in dims:
        rec[col] = _number(g(label))
        if g(label) and not rec[col]:
            flags.append(f"{col}_not_number")
    if rec["foundation_type"] == "circle" and rec["foundation_width_y"]:
        flags.append("foundation_width_y_on_circle")

    rec["design_standard_text"] = g("規格")
    rec["wind_speed_text"] = g("設計風速(m/s)")
    rec["opening_height"] = g("開口部高さ")
    rec["concrete_strength"] = norm_concrete(g("ｺﾝｸﾘｰﾄ強度"))
    rec["opening_direction_note"] = g("開口部方向")

    flags += missing_flags(rec, ("receipt_no", "requester_pic_name"))
    return rec, flags
