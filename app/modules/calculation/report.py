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
from app.modules.calculation.display import check_status
from app.modules.calculation.schemas import (
    CalculationReport,
    ReportDirectObject,
    ReportFoundationLoads,
    ReportGeometry,
    ReportLoadRow,
    ReportOverallCheck,
    ReportSection,
    ReportSpecification,
    ReportStepPole,
    ReportArm,
    ReportArmObject,
    ReportArmResult,
    ReportOverheadWire,
    ReportOverheadWireResult
)



class ReportTemplateUnavailable(Exception):
    """Design standard run belum punya template laporan."""


# ===== Geometri yang dihitung (semua template) =====
# Kebalikan builder: nama jenis Calculation Service kembali ke enum gateway.
_POLE_TYPES = {name: kind for kind, name in builder.ENGINE_POLE_TYPES.items()}
_OBJECT_KINDS = {name: kind for kind, name in builder.ENGINE_OBJECT_TYPES.items()}


def _step_pole(pole: dict) -> ReportStepPole:
    # kolom lower/upper selalu ada, upper null untuk straight.
    return ReportStepPole(
        name=pole["name"],
        pole_type=_POLE_TYPES[pole["pole_type"]],
        material_name=pole["material"],
        top_elevation_m=pole["top_elevation_m"],
        diameter_lower_mm=pole["diameter_lower_mm"],
        diameter_upper_mm=pole["diameter_upper_mm"],
        thickness_lower_mm=pole["thickness_lower_mm"],
        thickness_upper_mm=pole["thickness_upper_mm"],
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
    

def _arm_object(obj: dict) -> ReportArmObject:
    return ReportArmObject.model_validate({**obj, "object_kind": _OBJECT_KINDS[obj["object_type"]]})


def _arm(arm: dict) -> ReportArm:
    return ReportArm.model_validate({
        **arm,
        "material_name": arm["material"],
        "objects": [_arm_object(o) for o in arm["objects"]],
    })


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
        overhead_wires=[ReportOverheadWire.model_validate(w) for w in engine_request["overhead_wires"]],
        arms=[_arm(a) for a in engine_request["arms"]],
    )

# ===== Design standard 3 (Old Lighting Pole) =====
OLD_LIGHTING_POLE_TEMPLATE = "old_lighting_pole"
# Laporan Old Lighting Pole memakai arah angin lurus. Gateway tidak meminta arah miring.
OLD_LIGHTING_POLE_WIND_CASE = "STRAIGHT"
OLD_LIGHTING_POLE_CHECK = "pole_bending"
OLD_LIGHTING_POLE_ARM_CHECK = "arm_bending"


def _by_key(rows: list[dict], key: str, value: str) -> dict:
    for row in rows:
        if row[key] == value:
            return row
    raise ValueError(f"Calculation Service response has no {key} {value}")


def _load_row(row: dict) -> ReportLoadRow:
    # kind dari Calculation Service (ARM, DIRECT_OBJECT, ...) ditulis huruf kecil.
    return ReportLoadRow.model_validate({**row, "kind": row["kind"].lower()})


def _pole_specification(pole: dict) -> ReportSpecification:
    return ReportSpecification.model_validate({
        **pole,
        "component": "pole",
        "pole_type": _POLE_TYPES[pole["pole_type"]],
        "material_name": pole["material"],
    })


def _arm_specification(arm: dict, sent: dict) -> ReportSpecification:
    # Ukuran dan material dari payload; nilai penampang dari jawaban Calculation Service.
    specification = arm["specification"]
    return ReportSpecification(
        component="arm",
        name=arm["name"],
        material_name=sent["material"],
        diameter_mm=sent["diameter_mm"],
        thickness_mm=sent["thickness_mm"],
        cross_section_area_cm2=specification["section_area_cm2"],
        moment_of_inertia_cm4=specification["moment_of_inertia_cm4"],
        radius_of_gyration_cm=specification["radius_of_gyration_cm"],
        unit_weight_kg_m=specification["unit_weight_kg_m"],
    )


def _specifications(run: CalculationRun) -> list[ReportSpecification]:
    """Step pole lalu lengan, urutan apa adanya dari Calculation Service (sama dengan payload)."""
    data = run.result_snapshot["data"]
    sent_arms = {a["name"]: a for a in run.input_snapshot["engine_request"]["arms"]}
    return [_pole_specification(p) for p in data["pole_sections"]] + [
        _arm_specification(a, sent_arms[a["name"]]) for a in data["arms"]
    ]


def _old_lighting_pole_section(position: dict) -> ReportSection:
    section = position["section"]
    wind_case = _by_key(position["wind_cases"], "code", OLD_LIGHTING_POLE_WIND_CASE)
    totals = wind_case["totals"]
    check = _by_key(wind_case["checks"], "check", OLD_LIGHTING_POLE_CHECK)
    return ReportSection(
        evaluated_position_m=position["evaluated_position_m"],
        pole_name=position["pole_name"],
        material_name=section["material"],
        diameter_mm=section["diameter_mm"],
        thickness_mm=section["thickness_mm"],
        section_modulus_cm3=section["section_modulus_cm3"],
        # Urutan baris apa adanya dari Calculation Service.
        rows=[_load_row(r) for r in wind_case["load_rows"]],
        vertical_load_n=position["vertical_fix_load_n"],
        wind_load_n=totals["wind_load_n"],
        wind_tension_n=totals["wind_tension_n"],
        horizontal_load_n=totals["resultant_horizontal_load_n"],
        arm_fix_load_moment_nm=totals["arm_fix_load_moment_nm"],
        combined_moment_x_nm=totals["combined_moment_x_nm"],
        combined_moment_y_nm=totals["combined_moment_y_nm"],
        bending_moment_nm=check["moment_nm"],
        calculated_stress_n_mm2=check["stress_n_mm2"],
        allowable_stress_n_mm2=check["allowable_stress_n_mm2"],
        utilization_ratio=check["utilization_ratio"],
        status=check_status(check["status"]),
    )
    

def _old_lighting_pole_arm(arm: dict) -> ReportArmResult:
    totals = arm["totals"]
    check = _by_key(arm["checks"], "check", OLD_LIGHTING_POLE_ARM_CHECK)
    return ReportArmResult(
        name=arm["name"],
        specification=arm["specification"],
        # Urutan apa adanya: badan lengan lalu objek dari yang terjauh.
        loads=arm["objects"],
        total_fix_load_n=totals["fix_load_n"],
        total_fix_load_moment_nm=totals["fix_load_moment_nm"],
        total_wind_moment_nm=totals["wind_moment_nm"],
        bending_moment_nm=check["moment_nm"],
        calculated_stress_n_mm2=check["stress_n_mm2"],
        allowable_stress_n_mm2=check["allowable_stress_n_mm2"],
        utilization_ratio=check["utilization_ratio"],
        status=check_status(check["status"]),
    )


def _old_lighting_pole_wire(wire: dict) -> ReportOverheadWireResult:
    wind_case = _by_key(wire["wind_cases"], "code", OLD_LIGHTING_POLE_WIND_CASE)
    return ReportOverheadWireResult(
        name=wire["name"],
        wind_coefficient=wire["wind_coefficient"],
        fix_load_per_length_n_m=wire["fix_load_per_length_n_m"],
        fixed_tension_n=wire["fixed_tension_n"],
        combined_wind_line_load_n_m=wind_case["combined_wind_line_load_n_m"],
        wind_tension_n=wind_case["wind_tension_n"],
    )


def _old_lighting_pole_report(run: CalculationRun) -> CalculationReport:
    data = run.result_snapshot["data"]
    context = run.input_snapshot["context"]
    conditions = data["conditions"]
    # Satu bagian per posisi cek yang ada di run, dari yang tertinggi. Tiang dengan
    # satu posisi cek (IS: dasar tiang) hanya punya satu bagian.
    positions = sorted(data["evaluated_positions"], key=lambda p: p["evaluated_position_m"], reverse=True)
    sections = [_old_lighting_pole_section(p) for p in positions]
    base = sections[-1]
    return CalculationReport(
        run_id=run.id,
        template=OLD_LIGHTING_POLE_TEMPLATE,
        design_standard_code=context["design_standard_code"],
        design_standard_name=context["design_standard_name"],
        wind_case=OLD_LIGHTING_POLE_WIND_CASE,
        design_wind_speed_m_s=conditions["wind_speed_m_s"],
        wind_pressure_n_m2=conditions["wind_pressure_n_m2"],
        allowable_stress_n_mm2=base.allowable_stress_n_mm2,
        geometry=_geometry(run),
        specifications=_specifications(run),
        sections=sections,
        arms=[_old_lighting_pole_arm(a) for a in data["arms"]],
        overhead_wires=[_old_lighting_pole_wire(w) for w in data["overhead_wires"]],
        foundation=ReportFoundationLoads(
            vertical_load_n=base.vertical_load_n,
            horizontal_load_n=base.horizontal_load_n,
            bending_moment_nm=base.bending_moment_nm,
        ),
        overall=ReportOverallCheck.model_validate({**data["summary"]["governing"], "status": run.status}),
    )


# Kunci = design_standards.code yang tercatat di input_snapshot run.
REPORT_TEMPLATES: dict[int, Callable[[CalculationRun], CalculationReport]] = {
    3: _old_lighting_pole_report,
}


def format_report(run: CalculationRun) -> CalculationReport:
    """Hanya untuk run ok atau ng. Run failed tidak punya result_snapshot."""
    code = run.input_snapshot["context"]["design_standard_code"]
    template = REPORT_TEMPLATES.get(code)
    if template is None:
        raise ReportTemplateUnavailable(code)
    return template(run)