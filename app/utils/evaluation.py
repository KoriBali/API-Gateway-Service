from app.utils.base_schema import CamelBaseModel


class EvaluationRow(CamelBaseModel):
    """Satu baris pada tabel hasil (mis. satu kondisi angin pada satu pole)."""
    no: int
    description: str = ""

    # nilai MESIN (angka), bukan teks tampilan
    safety_factor: float          

    # "ok" | "ng" — nilai MESIN
    status: str                   


class EvaluationSection(CamelBaseModel):
    """Kelompok baris dengan judul (mis. 'Direct Wind Condition A')."""
    # key mesin stabil, mis. "direct_wind_a"
    key: str                      

    # teks tampilan, mis. "Direct Wind Condition A"
    label: str                    
    rows: list[EvaluationRow] = []


class EvaluationGroup(CamelBaseModel):
    """Satu subjek yang dievaluasi (mis. 'Pole 1' — berasal dari satu StepPole)."""
    name: str
    
    # "ok" | "ng" ringkasan grup
    status: str                   
    sections: list[EvaluationSection] = []


class EvaluationResult(CamelBaseModel):
    """Amplop hasil evaluasi generik. Dipakai lintas modul perhitungan."""
    # "ok" | "ng" ringkasan keseluruhan
    status: str                   
    groups: list[EvaluationGroup] = []