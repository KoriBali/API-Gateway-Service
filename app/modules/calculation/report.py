"""Formatter laporan: data laporan sebuah run menurut template design standard-nya.

Template dipilih dari design standard yang tercatat di input_snapshot run, bukan
dari kondisi request saat ini dan bukan dari tipe tiang, supaya laporan run lama
tidak berganti template. Preview di frontend dan file final memakai keluaran yang
sama. Nilai diambil apa adanya dari result_snapshot (sudah dibulatkan Calculation
Service); formatter hanya memilih dan menyusun.
"""
from collections.abc import Callable

from app.database.models.calculation import CalculationRun
from app.modules.calculation import builder
from app.modules.calculation.display import check_status, direction_row
from app.modules.calculation.schemas import (
    CalculationReport,
    ReportDirectObject,
    ReportFoundationLoads,
    ReportGeometry,
    ReportLoadRow,
    ReportOverallCheck,
    ReportSection,
    ReportStepPole,
)



class ReportTemplateUnavailable(Exception):
    """Design standard run belum punya template laporan."""


# Calculation Service menghitung satu unit per segmen tiang.
POLE_QUANTITY = 1

# ===== Geometri yang dihitung (semua template) =====
# Kebalikan builder: nama jenis Calculation Service kembali ke enum gateway.
_POLE_TYPES = {name: kind for kind, name in builder.ENGINE_POLE_TYPES.items()}
_OBJECT_KINDS = {name: kind for kind, name in builder.ENGINE_OBJECT_TYPES.items()}


def _step_pole(pole: dict) -> ReportStepPole:
    pole_type = _POLE_TYPES[pole["pole_type"]]
    if "diameter_lower_mm" in pole:
        lower = (pole["diameter_lower_mm"], pole["thickness_lower_mm"])
        upper = (pole["diameter_upper_mm"], pole["thickness_upper_mm"])
    else:
        # Straight dikirim dengan satu ukuran (diameter_mm, thickness_mm).
        lower, upper = (pole["diameter_mm"], pole["thickness_mm"]), (None, None)
    return ReportStepPole(
        name=pole["name"],
        pole_type=pole_type,
        material_name=pole["material"],
        top_elevation_m=pole["top_elevation_m"],
        diameter_lower_mm=lower[0],
        diameter_upper_mm=upper[0],
        thickness_lower_mm=lower[1],
        thickness_upper_mm=upper[1],
    )


def _direct_object(obj: dict) -> ReportDirectObject:
    return ReportDirectObject(
        name=obj["name"],
        object_kind=_OBJECT_KINDS[obj["object_type"]],
        front_area_m2=obj["front_area_m2"],
        side_area_m2=obj.get("side_area_m2"),
        fixed_angle_deg=obj.get("fixed_angle_deg"),
        mass_per_unit_kg=obj["mass_per_unit_kg"],
        elevation_m=obj["elevation_m"],
        base_wind_coefficient=obj["base_wind_coefficient"],
        quantity=obj["quantity"],
    )


def _geometry(run: CalculationRun) -> ReportGeometry:
    """Dari payload yang benar-benar dikirim ke Calculation Service, supaya laporan
    menggambarkan run ini walau case sudah disimpan ulang dengan tinggi lain."""
    engine_request = run.input_snapshot["engine_request"]
    context = run.input_snapshot["context"]
    return ReportGeometry(
        pole_standard_name=context["pole_standard_name"],
        pole_standard_height=context["pole_standard_height"],
        ground_position=context["ground_position"],
        gl_elevation_m=context["gl_elevation_m"],
        step_poles=[_step_pole(p) for p in engine_request["poles"]],
        direct_objects=[_direct_object(o) for o in engine_request["direct_objects"]],
    )

# ===== Design standard 3 (Old JIL) =====
OLD_JIL_TEMPLATE = "old_jil"
# Laporan Old JIL hanya menampilkan arah N dari delapan arah yang dihitung.
OLD_JIL_DIRECTION = "N"


def _object_row(obj: dict) -> ReportLoadRow:
    wind = direction_row(obj["directional_results"], OLD_JIL_DIRECTION)
    return ReportLoadRow(
        kind="direct_object",
        name=obj["object_name"],
        unit_weight_n=obj["weight_per_unit_n"],
        quantity=obj["quantity"],
        fix_load_n=obj["fix_load_n"],
        projected_area_per_unit_m2=wind["projected_area_per_unit_m2"],
        wind_coefficient=obj["cf"],
        wind_load_per_unit_n=wind["wind_load_per_unit_n"],
        wind_quantity=obj["quantity"],
        wind_load_n=wind["wind_load_n"],
    )


def _pole_row(pole: dict) -> ReportLoadRow:
    # Beban angin segmen tiang tidak bergantung arah.
    return ReportLoadRow(
        kind="pole",
        name=pole["geometry"]["pole_name"],
        unit_weight_n=pole["weight_n"],
        quantity=POLE_QUANTITY,
        fix_load_n=pole["fix_load_n"],
        projected_area_per_unit_m2=pole["projected_area_m2"],
        wind_coefficient=pole["cf"],
        wind_load_per_unit_n=pole["wind_load_n"],
        wind_quantity=POLE_QUANTITY,
        wind_load_n=pole["wind_load_n"],
    )


def _old_jil_section(position: dict) -> ReportSection:
    check = position["section_check"]
    section = check["section_properties"]
    wind = direction_row(check["directional_results"], OLD_JIL_DIRECTION)
    strength = wind["wind_strength"]
    # direct_object bernilai null bila case tanpa objek langsung.
    objects = (position.get("direct_object") or {}).get("direct_object_results") or []
    # Segmen dari yang teratas, sama dengan urutan baris template.
    poles = sorted(position["pole"]["pole_results"], key=lambda p: p["geometry"]["segment_top_m"], reverse=True)
    return ReportSection(
        evaluated_position_m=position["evaluated_position_m"],
        pole_name=check["evaluated_pole_name"],
        material_name=check["material_name"],
        diameter_mm=section["diameter_mm"],
        thickness_mm=section["thickness_mm"],
        section_modulus_cm3=section["section_modulus_cm3"],
        rows=[_object_row(o) for o in objects] + [_pole_row(p) for p in poles],
        vertical_load_n=check["total_fix_load_n"],
        horizontal_load_n=wind["total_wind_load_n"],
        bending_moment_nm=wind["combined_wind_moment_nm"],
        calculated_stress_n_mm2=strength["calculated_stress_n_mm2"],
        allowable_stress_n_mm2=strength["allowable_stress_n_mm2"],
        utilization_ratio=strength["utilization_ratio"],
        status=check_status(strength["status"]),
    )


def _overall(run: CalculationRun, positions: list[dict]) -> ReportOverallCheck:
    """Rasio terbesar di semua posisi dan kedelapan arah. Bila sama besar, yang lebih dulu."""
    candidates = [
        (position["evaluated_position_m"], row)
        for position in positions
        for row in position["section_check"]["directional_results"]
    ]
    elevation, row = max(candidates, key=lambda c: c[1]["wind_strength"]["utilization_ratio"])
    return ReportOverallCheck(
        status=run.status,
        evaluated_position_m=elevation,
        direction=row["direction"],
        utilization_ratio=row["wind_strength"]["utilization_ratio"],
    )


def _old_jil_report(run: CalculationRun) -> CalculationReport:
    data = run.result_snapshot["data"]
    context = run.input_snapshot["context"]
    # Satu bagian per posisi cek yang ada di run, dari yang tertinggi. Tiang dengan
    # satu posisi cek (IS: dasar tiang) hanya punya satu bagian.
    positions = sorted(data["evaluated_positions"], key=lambda p: p["evaluated_position_m"], reverse=True)
    sections = [_old_jil_section(p) for p in positions]
    base = sections[-1]
    return CalculationReport(
        run_id=run.id,
        template=OLD_JIL_TEMPLATE,
        design_standard_code=context["design_standard_code"],
        design_standard_name=context["design_standard_name"],
        report_direction=OLD_JIL_DIRECTION,
        design_wind_speed_m_s=data["design_condition"]["wind"]["design_wind_speed_m_s"],
        # Standar 2 sampai 5: q sama di semua elevasi, jadi cukup dari segmen pertama.
        wind_pressure_n_m2=positions[0]["pole"]["pole_results"][0]["wind_pressure_n_m2"],
        allowable_stress_n_mm2=base.allowable_stress_n_mm2,
        geometry=_geometry(run),
        sections=sections,
        foundation=ReportFoundationLoads(
            vertical_load_n=base.vertical_load_n,
            horizontal_load_n=base.horizontal_load_n,
            bending_moment_nm=base.bending_moment_nm,
        ),
        overall=_overall(run, positions),
    )


# Kunci = design_standards.code yang tercatat di input_snapshot run.
REPORT_TEMPLATES: dict[int, Callable[[CalculationRun], CalculationReport]] = {
    3: _old_jil_report,
}


def format_report(run: CalculationRun) -> CalculationReport:
    """Hanya untuk run ok atau ng. Run failed tidak punya result_snapshot."""
    code = run.input_snapshot["context"]["design_standard_code"]
    template = REPORT_TEMPLATES.get(code)
    if template is None:
        raise ReportTemplateUnavailable(code)
    return template(run)