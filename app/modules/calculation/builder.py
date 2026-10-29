"""Penyusun payload POST /api/pole/calculate dan pembaca status run.

Fungsi murni: tidak membaca DB dan tidak memanggil Calculation Service, supaya
Hitung (G14) dan Simpan (G15) memakai kode yang sama persis. Kolom geometri
bernama sama dengan kontrak Calculation Service, sehingga nilai cukup disalin.
"""
import enum
from decimal import Decimal

from app.database.models.calculation import GroundPosition, StatusCalculationRun
from app.database.models.geometry import ObjectKind, PoleType
from app.database.models.master import PoleHeightGroundPosition

# Standar 2 sampai 5: tekanan angin konstan di Calculation Service, cukup
# design_standard + structure_height_m. Standar 1 dan 6 butuh kategori atmosfer
# yang belum punya kolom. Nomor 7 (New JIL) belum diterima.
FIXED_WIND_DESIGN_STANDARDS = frozenset({2, 3, 4, 5})

# Elevasi diukur dari dasar tiang.
BASE_ELEVATION_M = 0.0

# Ground position case diturunkan dari baris katalog tinggi yang dipilih. under_gl =
# baseplate di bawah GL. embedment (baris katalog yang sama, tanpa baseplate) belum bisa
# dipilih sampai ada langkah baseplate/foundation. upper_gl tidak punya baris katalog.
CASE_GROUND_POSITION = {
    PoleHeightGroundPosition.on_gl: GroundPosition.on_gl,
    PoleHeightGroundPosition.under_gl: GroundPosition.under_gl,
}

# Nama jenis di kontrak Calculation Service. Dipakai juga laporan untuk membaca balik snapshot.
ENGINE_POLE_TYPES = {PoleType.taper: "Taper", PoleType.straight: "Straight"}
ENGINE_OBJECT_TYPES = {ObjectKind.omni: "Omni", ObjectKind.directional: "Directional"}

class RunSkipReason(str, enum.Enum):
    """Alasan Simpan tidak membuat run. Input tetap tersimpan."""
    wind_speed_missing = "wind_speed_missing"
    design_standard_not_calculable = "design_standard_not_calculable"
    pole_height_not_calculable = "pole_height_not_calculable"
    engine_unavailable = "engine_unavailable"


RUN_SKIP_MESSAGES = {
    RunSkipReason.wind_speed_missing: "Calculation conditions have no wind speed",
    RunSkipReason.design_standard_not_calculable: "The design standard cannot be calculated yet",
    RunSkipReason.pole_height_not_calculable: "The selected pole height has no catalog geometry yet",
    RunSkipReason.engine_unavailable: "Calculation Service is unavailable; try again later",
}


def run_skip_reason(conditions, design_standard, height) -> RunSkipReason | None:
    """Prasyarat run (G15). Diperiksa sesudah input tersimpan."""
    if conditions.wind_speed is None:
        return RunSkipReason.wind_speed_missing
    if design_standard.code not in FIXED_WIND_DESIGN_STANDARDS:
        return RunSkipReason.design_standard_not_calculable
    if not height.is_calculable:
        return RunSkipReason.pole_height_not_calculable
    return None


def _num(value: Decimal | float | int) -> float:
    return float(value)


def build_pole_request(
    *,
    design_standard_code: int,
    segments,
    material_names: dict[str, str],
    direct_objects,
    evaluated_positions_m,
) -> dict:
    """segments: baris berbentuk PoleSegmentColumnsMixin + material_id.
    direct_objects: baris atau input berbentuk DirectObjectColumnsMixin."""
    poles = []
    # Urut dari puncak tertinggi, sama dengan payload contoh. Calculation Service
    # mengurutkan ulang menurut top_elevation_m, jadi urutan tidak mengubah hasil.
    for segment in sorted(segments, key=lambda s: s.top_elevation_m, reverse=True):
        pole = {
            "name": segment.name,
            "pole_type": ENGINE_POLE_TYPES[segment.pole_type],
            "material": material_names[segment.material_id],
            "top_elevation_m": _num(segment.top_elevation_m),
        }
        if segment.pole_type == PoleType.taper:
            pole["diameter_lower_mm"] = _num(segment.diameter_lower_mm)
            pole["diameter_upper_mm"] = _num(segment.diameter_upper_mm)
            pole["thickness_lower_mm"] = _num(segment.thickness_lower_mm)
            pole["thickness_upper_mm"] = _num(segment.thickness_upper_mm)
        else:
            # Straight: kolom lower adalah satu-satunya ukuran.
            pole["diameter_mm"] = _num(segment.diameter_lower_mm)
            pole["thickness_mm"] = _num(segment.thickness_lower_mm)
        # quantity segmen sengaja tidak dikirim.
        poles.append(pole)

    objects = []
    for obj in sorted(direct_objects, key=lambda o: o.name):
        item = {
            "name": obj.name,
            "object_type": ENGINE_OBJECT_TYPES[obj.object_kind],
            "front_area_m2": _num(obj.front_area_m2),
            "mass_per_unit_kg": _num(obj.mass_per_unit_kg),
            "elevation_m": _num(obj.elevation_m),
            "base_wind_coefficient": _num(obj.base_wind_coefficient),
            "quantity": obj.quantity,
        }
        if obj.object_kind == ObjectKind.directional:
            item["side_area_m2"] = _num(obj.side_area_m2)
            item["fixed_angle_deg"] = _num(obj.fixed_angle_deg)
        objects.append(item)

    body = {
        "wind": {
            "design_standard": design_standard_code,
            "structure_height_m": max(p["top_elevation_m"] for p in poles),
        },
        "base_elevation_m": BASE_ELEVATION_M,
        "poles": poles,
        "direct_objects": objects,
        "evaluated_positions_m": [_num(p) for p in evaluated_positions_m],
    }
    # overdesign_factor tidak dikirim: Calculation Service memakai 1
    return body


def build_context(*, conditions, design_standard, height) -> dict:
    """Bagian context input_snapshot: data gateway yang dipakai menyusun payload."""
    return {
        "design_standard_id": design_standard.id,
        "design_standard_name": design_standard.name,
        "design_standard_code": design_standard.code,
        "wind_speed": _num(conditions.wind_speed) if conditions.wind_speed is not None else None,
        "air_density": _num(conditions.air_density),
        "pole_standard_id": height.pole_standard_id,
        "pole_standard_name": height.pole_standard.name,
        "pole_standard_height_id": height.id,
        "pole_standard_height": _num(height.height),
        "ground_position": CASE_GROUND_POSITION[height.ground_position].value,
        "gl_elevation_m": _num(height.gl_elevation_m) if height.gl_elevation_m is not None else None,
    }


def derive_status(result_body: dict) -> StatusCalculationRun:
    """ok bila seluruh pengecekan O.K, ng bila ada yang lain.

    Dibaca dari section_check tiap posisi dan tiap arah, untuk kekuatan angin dan
    seismik. Jawaban tanpa satu pun status dianggap tidak dikenali (ValueError),
    karena run tidak boleh menyatakan lolos tanpa pengecekan.
    """
    statuses = []
    for position in result_body["data"]["evaluated_positions"]:
        check = position.get("section_check") or {}
        for row in check.get("directional_results") or []:
            for key in ("wind_strength", "seismic_strength"):
                strength = row.get(key)
                if strength is not None:
                    statuses.append(strength.get("status"))
    if not statuses:
        raise ValueError("Calculation Service response has no strength status")
    if all(s == "O.K" for s in statuses):
        return StatusCalculationRun.ok
    return StatusCalculationRun.ng