"""Formatter tampilan: ringkasan O.K/N.G per posisi cek dan per arah.

Fungsi murni atas jawaban Calculation Service, dipakai Hitung dan pembacaan run.
Nilai diambil apa adanya, karena sudah dibulatkan Calculation Service. Formatter
hanya memilih dan menyusun, tidak menghitung ulang dan tidak membulatkan.
"""
from app.modules.calculation import builder
from app.modules.calculation.schemas import (
    CalculationDisplay,
    CheckStatus,
    DirectionCheck,
    PositionCheck,
)

# Teks status lolos dari Calculation Service. Nilai lain dibaca sebagai N.G.
ENGINE_OK = "O.K"


def check_status(engine_status: str | None) -> CheckStatus:
    return "ok" if engine_status == ENGINE_OK else "ng"


def position_status(section_check: dict) -> CheckStatus:
    """Aturan yang sama dengan status run, dibatasi pada satu posisi cek."""
    for row in section_check["directional_results"]:
        for key in ("wind_strength", "seismic_strength"):
            strength = row.get(key)
            if strength is not None and strength.get("status") != ENGINE_OK:
                return "ng"
    return "ok"


def direction_check(row: dict) -> DirectionCheck:
    wind = row["wind_strength"]
    return DirectionCheck(
        direction=row["direction"],
        resultant_wind_load_n=row["resultant_wind_load_n"],
        combined_wind_moment_nm=row["combined_wind_moment_nm"],
        calculated_stress_n_mm2=wind["calculated_stress_n_mm2"],
        allowable_stress_n_mm2=wind["allowable_stress_n_mm2"],
        utilization_ratio=wind["utilization_ratio"],
        status=check_status(wind["status"]),
    )


def format_display(result_body: dict) -> CalculationDisplay:
    positions = []
    for position in result_body["data"]["evaluated_positions"]:
        check = position["section_check"]
        section = check["section_properties"]
        directions = [direction_check(row) for row in check["directional_results"]]
        # max() mengembalikan yang pertama bila sama besar, jadi urutan Calculation Service menentukan.
        governing = max(directions, key=lambda d: d.utilization_ratio)
        positions.append(PositionCheck(
            evaluated_position_m=position["evaluated_position_m"],
            pole_name=check["evaluated_pole_name"],
            material_name=check["material_name"],
            diameter_mm=section["diameter_mm"],
            thickness_mm=section["thickness_mm"],
            section_modulus_cm3=section["section_modulus_cm3"],
            total_fix_load_n=check["total_fix_load_n"],
            status=position_status(check),
            governing_direction=governing.direction,
            directions=directions,
        ))
    return CalculationDisplay(
        status=builder.derive_status(result_body).value,
        positions=positions,
    )