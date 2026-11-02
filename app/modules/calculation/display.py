"""Formatter tampilan: status run, pengecekan penentu, dan setiap pengecekan kekuatan.

Fungsi murni atas jawaban Calculation Service, dipakai Hitung dan pembacaan run.
Nilai diambil apa adanya, karena sudah dibulatkan Calculation Service. Formatter
hanya memilih dan menyusun, tidak menghitung ulang dan tidak membulatkan.
"""
from app.modules.calculation import builder
from app.modules.calculation.schemas import CalculationDisplay, CheckStatus, DisplayCheck, DisplayGoverning

# Teks status lolos dari Calculation Service. Nilai lain dibaca sebagai NG.
ENGINE_OK = "OK"


def check_status(engine_status: str | None) -> CheckStatus:
    return "ok" if engine_status == ENGINE_OK else "ng"


def _checks(result_body: dict) -> list[DisplayCheck]:
    """Tiang: per posisi cek lalu per wind case, urut sama dengan jawaban. Lengan sesudahnya."""
    data = result_body["data"]
    rows = []
    for position in data["evaluated_positions"]:
        for wind_case in position["wind_cases"]:
            for check in wind_case["checks"]:
                rows.append(DisplayCheck(
                    component="pole",
                    name=position["pole_name"],
                    evaluated_position_m=position["evaluated_position_m"],
                    wind_case=wind_case["code"],
                    check=check["check"],
                    utilization_ratio=check["utilization_ratio"],
                    status=check["status"],
                ))
    for arm in data["arms"]:
        for check in arm["checks"]:
            rows.append(DisplayCheck(
                component="arm",
                name=arm["name"],
                check=check["check"],
                utilization_ratio=check["utilization_ratio"],
                status=check["status"],
            ))
    return rows


def format_display(result_body: dict) -> CalculationDisplay:
    run_status, _ = builder.read_summary(result_body)
    return CalculationDisplay(
        status=run_status.value,
        governing=DisplayGoverning.model_validate(result_body["data"]["summary"]["governing"]),
        checks=_checks(result_body),
    )