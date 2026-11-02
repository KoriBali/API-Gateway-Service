"""Penyusun payload POST /api/pole/calculate dan pembaca status run.

Fungsi murni: tidak membaca DB dan tidak memanggil Calculation Service, supaya
Hitung dan Simpan memakai kode yang sama persis. Kolom geometri
bernama sama dengan kontrak Calculation Service, sehingga nilai cukup disalin.
"""
import enum
from decimal import Decimal

from app.database.models.calculation import GroundPosition, StatusCalculationRun
from app.database.models.geometry import ObjectKind, PoleType
from app.database.models.master import PoleHeightGroundPosition

# Versi kontrak POST /api/pole/calculate yang disusun dan dibaca gateway. Jawaban
# dengan versi lain tidak dikenali.
ENGINE_SCHEMA_VERSION = "2.0"

# design_standards.code yang diterima Calculation Service kontrak 2.0. Code lain ditolak
# 422 oleh Calculation Service, jadi Simpan tidak membuat run untuknya.
CALCULABLE_DESIGN_STANDARDS = frozenset({3})

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
    if design_standard.code not in CALCULABLE_DESIGN_STANDARDS:
        return RunSkipReason.design_standard_not_calculable
    if not height.is_calculable:
        return RunSkipReason.pole_height_not_calculable
    return None


def _num(value: Decimal | float | int) -> float:
    return float(value)


def _num_or_none(value: Decimal | float | int | None) -> float | None:
    return None if value is None else float(value)


def build_pole_request(
    *,
    design_standard_code: int,
    segments,
    material_names: dict[str, str],
    direct_objects,
    evaluated_positions_m,
) -> dict:
    """segments: baris berbentuk PoleSegmentColumnsMixin + material_id.
    direct_objects: baris atau input berbentuk DirectObjectColumnsMixin.

    Kolom disalin apa adanya, termasuk NULL: upper segmen straight dan arah hadap
    objek omni dikirim null dan diabaikan Calculation Service.
    """
    poles = []
    # Urut dari puncak tertinggi, sama dengan payload contoh. Calculation Service
    # mengurutkan ulang menurut top_elevation_m, jadi urutan tidak mengubah hasil.
    for segment in sorted(segments, key=lambda s: s.top_elevation_m, reverse=True):
        poles.append({
            "name": segment.name,
            "pole_type": ENGINE_POLE_TYPES[segment.pole_type],
            "material": material_names[segment.material_id],
            "top_elevation_m": _num(segment.top_elevation_m),
            "diameter_lower_mm": _num(segment.diameter_lower_mm),
            "diameter_upper_mm": _num_or_none(segment.diameter_upper_mm),
            "thickness_lower_mm": _num(segment.thickness_lower_mm),
            "thickness_upper_mm": _num_or_none(segment.thickness_upper_mm),
        })
        # quantity segmen sengaja tidak dikirim.

    objects = [
        {
            "name": obj.name,
            "object_type": ENGINE_OBJECT_TYPES[obj.object_kind],
            "front_area_m2": _num(obj.front_area_m2),
            "side_area_m2": _num_or_none(obj.side_area_m2),
            "fixed_angle_deg": _num_or_none(obj.fixed_angle_deg),
            "mass_per_unit_kg": _num(obj.mass_per_unit_kg),
            "elevation_m": _num(obj.elevation_m),
            "base_wind_coefficient": _num(obj.base_wind_coefficient),
            "quantity": obj.quantity,
        }
        for obj in sorted(direct_objects, key=lambda o: o.name)
    ]

    # Tinggi struktur dihitung Calculation Service dari puncak segmen tertinggi.
    # overdesign_factor dan include_oblique_wind tidak dikirim: Calculation Service
    # memakai 1.0 dan arah lurus saja, sama dengan laporan Old JIL.
    return {
        "design_standard": design_standard_code,
        "base_elevation_m": BASE_ELEVATION_M,
        "poles": poles,
        "direct_objects": objects,
        "evaluated_positions_m": [_num(p) for p in evaluated_positions_m],
    }


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


# Status keseluruhan dari Calculation Service ke status run.
ENGINE_RUN_STATUSES = {"OK": StatusCalculationRun.ok, "NG": StatusCalculationRun.ng}


def read_summary(result_body: dict) -> tuple[StatusCalculationRun, float]:
    """Status run dan utilization_ratio pengecekan penentu, apa adanya dari summary.

    Jawaban dengan versi kontrak lain atau tanpa summary yang dikenali menimbulkan
    KeyError atau ValueError: run tidak boleh menyatakan lolos tanpa pengecekan.
    """
    data = result_body["data"]
    if data["schema_version"] != ENGINE_SCHEMA_VERSION:
        raise ValueError(f"Calculation Service answered schema {data['schema_version']!r}")
    summary = data["summary"]
    return ENGINE_RUN_STATUSES[summary["status"]], summary["governing"]["utilization_ratio"]