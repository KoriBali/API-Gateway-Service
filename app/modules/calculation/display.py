"""Formatter tampilan: rasio dan status per posisi cek pada arah design standard.

Fungsi murni atas jawaban Calculation Service, dipakai Hitung dan pembacaan run.
Nilai diambil apa adanya, karena sudah dibulatkan Calculation Service. Formatter
hanya memilih dan menyusun, tidak menghitung ulang dan tidak membulatkan.
"""
from app.modules.calculation import builder
from app.modules.calculation.schemas import CalculationDisplay, CheckStatus, PositionCheck

# Teks status lolos dari Calculation Service. Nilai lain dibaca sebagai N.G.
ENGINE_OK = "O.K"

# Arah yang ditampilkan per design_standards.code. Old JIL (3) hanya memakai arah N,
# sama dengan laporannya. Code lain belum ditentukan: tampilan hanya memuat status run.
DISPLAY_DIRECTIONS = {3: "N"}


def check_status(engine_status: str | None) -> CheckStatus:
    return "ok" if engine_status == ENGINE_OK else "ng"


def direction_row(rows: list[dict], direction: str) -> dict:
    """Satu baris arah dari directional_results. Dipakai juga formatter laporan."""
    for row in rows:
        if row["direction"] == direction:
            return row
    raise ValueError(f"Calculation Service response has no {direction} direction")


def format_display(result_body: dict, design_standard_code: int) -> CalculationDisplay:
    direction = DISPLAY_DIRECTIONS.get(design_standard_code)
    positions = []
    if direction is not None:
        for position in result_body["data"]["evaluated_positions"]:
            check = position["section_check"]
            # Rasio dan status sepasang dari pengecekan angin arah itu, apa adanya.
            strength = direction_row(check["directional_results"], direction)["wind_strength"]
            positions.append(PositionCheck(
                evaluated_position_m=position["evaluated_position_m"],
                evaluated_pole_name=check["evaluated_pole_name"],
                utilization_ratio=strength["utilization_ratio"],
                status=strength["status"],
            ))
    return CalculationDisplay(
        # Status run tetap dari kedelapan arah: arah miring bisa lebih buruk dari arah tampilan.
        status=builder.derive_status(result_body).value,
        display_direction=direction,
        positions=positions,
    )