"""Uraian 図番 (zuban, nomor request DataBank YP) saat intake. DD G11 dan invariant intake 9.

Hasil uraian hanya USULAN untuk form. Tidak pernah menolak input, dan tidak pernah
merangkai segmen kembali menjadi document_no.
"""
import re

from app.database.models.intake import BrandLine
from app.modules.intake.schemas import DocumentNoSegments


# head (huruf) + tail (2 huruf) + base (6 digit) + seq opsional sesudah "-" (boleh berhuruf, mis. -1B).
# Contoh: EPJ650117-1 -> head E, tail PJ, base 650117, seq 1.
_DOCUMENT_NO = re.compile(r"^(?P<head>[A-Z]+)(?P<tail>[A-Z]{2})(?P<base>\d{6})(?:-(?P<seq>[0-9A-Z]+))?$")

# Hanya tail yang mereknya sudah diketahui yang dicocokkan dengan brand_mark.
# Tail lain (mis. JP) tidak dicocokkan sampai artinya diketahui (DD L6).
_TAIL_BRAND = {"PJ": BrandLine.yp, "YS": BrandLine.ys}


class DocumentNoWarning:
    PATTERN_MISMATCH = "pattern_mismatch"
    TAIL_BRAND_MISMATCH = "tail_brand_mismatch"
    DUPLICATE = "duplicate_document_no"


def parse_document_no(value: str) -> DocumentNoSegments | None:
    """Pecah 図番 menjadi usulan segmen. None bila pola tidak cocok."""
    match = _DOCUMENT_NO.match(value)
    if match is None:
        return None
    return DocumentNoSegments(
        scope_code=match["head"],
        tail_code=match["tail"],
        pj_no=match["base"],
        record_no=match["seq"],
    )


def tail_matches_brand(tail_code: str, brand_mark: BrandLine | None) -> bool:
    """False hanya bila tail mereknya diketahui DAN berbeda dengan brand_mark yang dicentang."""
    expected = _TAIL_BRAND.get(tail_code)
    return expected is None or brand_mark is None or expected == brand_mark