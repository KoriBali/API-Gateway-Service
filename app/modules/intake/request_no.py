"""Uraian 図番 (zuban) YP saat intake. DD G11 dan invariant intake 9.

Sejak DD v0.9, 図番 utuh disimpan di requests.request_no (satu kolom dengan
依頼No YS). Hanya 図番 YP yang diurai; 依頼No YS tidak pernah diurai.

Hasil uraian hanya USULAN untuk form. Tidak pernah menolak input, dan tidak pernah
merangkai segmen kembali menjadi request_no (DD larangan 22).
"""
import re

from app.database.models.intake import BrandLine
from app.modules.intake.schemas import RequestNoSegments


# head (huruf) + tail (2 huruf) + base (6 digit) + seq opsional sesudah "-" (boleh berhuruf, mis. -1B).
# Contoh: EPJ650117-1 -> head E, tail PJ, base 650117, seq 1.
_REQUEST_NO_YP = re.compile(r"^(?P<head>[A-Z]+)(?P<tail>[A-Z]{2})(?P<base>\d{6})(?:-(?P<seq>[0-9A-Z]+))?$")

# Hanya tail yang mereknya sudah diketahui yang dicocokkan dengan brand_mark.
# Tail lain (mis. JP) tidak dicocokkan sampai artinya diketahui (DD L6).
_TAIL_BRAND = {"PJ": BrandLine.yp, "YS": BrandLine.ys}


class RequestNoWarning:
    PATTERN_MISMATCH = "pattern_mismatch"
    TAIL_BRAND_MISMATCH = "tail_brand_mismatch"
    DUPLICATE = "duplicate_request_no"


def parse_request_no(value: str) -> RequestNoSegments | None:
    """Pecah 図番 YP menjadi usulan segmen. None bila pola tidak cocok."""
    match = _REQUEST_NO_YP.match(value)
    if match is None:
        return None
    return RequestNoSegments(
        scope_code=match["head"],
        tail_code=match["tail"],
        pj_no=match["base"],
        record_no=match["seq"],
    )


def tail_matches_brand(tail_code: str, brand_mark: BrandLine | None) -> bool:
    """False hanya bila tail mereknya diketahui DAN berbeda dengan brand_mark yang dicentang."""
    expected = _TAIL_BRAND.get(tail_code)
    return expected is None or brand_mark is None or expected == brand_mark