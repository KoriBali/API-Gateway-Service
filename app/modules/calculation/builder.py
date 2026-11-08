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
ENGINE_SCHEMA_VERSION = "2.2"

# design_standards.code yang diterima Calculation Service kontrak 2.2. Code lain ditolak
# 422 oleh Calculation Service, jadi Simpan tidak membuat run untuknya.
CALCULABLE_DESIGN_STANDARDS = frozenset({3})

# Elevasi diukur dari dasar tiang.
BASE_ELEVATION_M = 0.0

# Ground position case yang boleh dipilih per baris katalog tinggi; yang pertama dipakai
# bila body tidak mengirim groundPosition. Dengan baseplate: on_gl atau under_gl. Tanpa
# baseplate: embedment, hanya dari baris on_gl, dan dihitung sama persis dengan on_gl karena
# ground position tidak dikirim ke Calculation Service. upper_gl tidak punya baris katalog.
GROUND_POSITION_CHOICES = {
    PoleHeightGroundPosition.on_gl: (GroundPosition.on_gl, GroundPosition.embedment),
    PoleHeightGroundPosition.under_gl: (GroundPosition.under_gl,),
}


def resolve_ground_position(height, requested: GroundPosition | None) -> GroundPosition | None:
    """Ground position case untuk pilihan tinggi ini. None = pilihan tidak tersedia."""
    choices = GROUND_POSITION_CHOICES[height.ground_position]
    if requested is None:
        return choices[0]
    return requested if requested in choices else None

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
    """Alasan run tidak bisa dibuat, None bila bisa. Simpan case memeriksanya sesudah input tersimpan."""
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
    wind_speed,
    air_density,
    step_poles,
    material_names: dict[str, str],
    direct_objects,
    overhead_wires,
    arms,
    evaluated_positions_m,
) -> dict:
    """wind_speed, air_density: dari calculation_conditions request, wajib terisi.
    step_poles: baris berbentuk StepPoleColumnsMixin + material_id.
    direct_objects: baris atau input berbentuk DirectObjectColumnsMixin.
    overhead_wires: baris atau input berkolom sama dengan overhead_wires.
    arms: baris atau input berbentuk ArmColumnsMixin + material_id + objects.
    material_names: nama material step pole dan lengan.

    """
    poles = []
    # Urut dari puncak tertinggi, sama dengan payload contoh. Calculation Service
    # mengurutkan ulang menurut top_elevation_m, jadi urutan tidak mengubah hasil.
    for step_pole in sorted(step_poles, key=lambda s: s.top_elevation_m, reverse=True):
        poles.append({
            "name": step_pole.name,
            "pole_type": ENGINE_POLE_TYPES[step_pole.pole_type],
            "material": material_names[step_pole.material_id],
            "top_elevation_m": _num(step_pole.top_elevation_m),
            "diameter_lower_mm": _num(step_pole.diameter_lower_mm),
            "diameter_upper_mm": _num_or_none(step_pole.diameter_upper_mm),
            "thickness_lower_mm": _num(step_pole.thickness_lower_mm),
            "thickness_upper_mm": _num_or_none(step_pole.thickness_upper_mm),
        })
        # quantity step pole sengaja tidak dikirim.

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
    
    wires = [
        {
            "name": wire.name,
            "mass_per_length_kg_m": _num(wire.mass_per_length_kg_m),
            "diameter_mm": _num(wire.diameter_mm),
            "elevation_m": _num(wire.elevation_m),
            "span_length_m": _num(wire.span_length_m),
            "sag_ratio_percent": _num(wire.sag_ratio_percent),
            "base_wind_coefficient": _num(wire.base_wind_coefficient),
            "fixed_angle_deg": _num(wire.fixed_angle_deg),
            "vertical_angle_deg": _num(wire.vertical_angle_deg),
        }
        for wire in sorted(overhead_wires, key=lambda w: w.name)
    ]

    arm_rows = [
        {
            "name": arm.name,
            "material": material_names[arm.material_id],
            "diameter_mm": _num(arm.diameter_mm),
            "thickness_mm": _num(arm.thickness_mm),
            "total_length_m": _num(arm.total_length_m),
            "exposed_length_m": _num(arm.exposed_length_m),
            "installation_height_m": _num(arm.installation_height_m),
            "fixed_angle_deg": _num(arm.fixed_angle_deg),
            "objects": [
                {
                    "name": obj.name,
                    "object_type": ENGINE_OBJECT_TYPES[obj.object_kind],
                    "front_area_m2": _num(obj.front_area_m2),
                    "side_area_m2": _num_or_none(obj.side_area_m2),
                    "mass_per_unit_kg": _num(obj.mass_per_unit_kg),
                    "horizontal_load_distance_m": _num(obj.horizontal_load_distance_m),
                    "base_wind_coefficient": _num(obj.base_wind_coefficient),
                    "quantity": obj.quantity,
                }
                for obj in sorted(arm.objects, key=lambda o: o.name)
            ],
        }
        for arm in sorted(arms, key=lambda a: a.name)
    ]

    # Tinggi struktur dihitung Calculation Service dari puncak step pole tertinggi.
    # overdesign_factor dan include_oblique_wind tidak dikirim: Calculation Service
    # memakai 1.0 dan arah lurus. Wind speed dan air density tidak punya default
    # di Calculation Service, jadi selalu dikirim.
    return {
        "design_standard": design_standard_code,
        "wind_speed_m_s": _num(wind_speed),
        "air_density_kg_m3": _num(air_density),
        "base_elevation_m": BASE_ELEVATION_M,
        "poles": poles,
        "direct_objects": objects,
        "overhead_wires": wires,
        "arms": arm_rows,
        "evaluated_positions_m": [_num(p) for p in evaluated_positions_m],
    }


def build_context(
    *, conditions, design_standard, height, ground_position: GroundPosition,
    embedment_length_mm: float | None,
) -> dict:
    """Bagian context input_snapshot: data gateway yang dipakai menyusun payload, ditambah
    isian laporan yang tidak dikirim (ground position, panjang tanam)."""
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
        "ground_position": ground_position.value,
        "gl_elevation_m": _num(height.gl_elevation_m) if height.gl_elevation_m is not None else None,
        "embedment_length_mm": embedment_length_mm,
    }


def run_stale_causes(case, run, conditions) -> list[str]:
    """Alasan run tidak lagi menggambarkan isian yang tersimpan. Kosong = run masih berlaku.
    input: isian disimpan lagi sesudah run dibuat (misalnya Simpan yang tidak membuat run).
    conditions: kondisi perhitungan request sekarang berbeda dari yang dipakai run."""
    causes = []
    if case.input_saved_at is not None and run.run_at < case.input_saved_at:
        causes.append("input")
    context = run.input_snapshot["context"]
    if conditions is None or (
        conditions.design_standard_id != context["design_standard_id"]
        or _num_or_none(conditions.wind_speed) != context["wind_speed"]
        or _num(conditions.air_density) != context["air_density"]
    ):
        causes.append("conditions")
    return causes


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