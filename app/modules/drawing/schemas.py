from datetime import datetime

from pydantic import Field, model_validator

from app.utils.base_schema import CamelBaseModel, snake_to_camel
from app.database.models.calculation import PoleKind
from app.database.models.drawing import DrawingType
from app.modules.calculation.schemas import CaseTitle



# ===== Drawing Case (header saja) =====
class DrawingCaseFields(CamelBaseModel):
    """Field header case gambar. Tabel anak (geometri, kopling, permukaan) menyusul
    bersama modul drawing lengkap."""
    title: CaseTitle | None = None
    case_label: str | None = None
    drawing_number: str | None = None
    part_number: str | None = None
    # Acuan perhitungan: calculation case di request yang sama. null = tanpa acuan.
    calculation_case_id: str | None = Field(default=None, min_length=1)


class DrawingCaseCreate(DrawingCaseFields):
    # Dipilih drafter saat case dibuat, tanpa nilai bawaan
    pole_kind: PoleKind
    # Kosong = diisi dari request_shared_details.drawing_type
    drawing_type: DrawingType | None = None


class DrawingCaseUpdate(DrawingCaseFields):
    pole_kind: PoleKind | None = None
    drawing_type: DrawingType | None = None

    @model_validator(mode="after")
    def _not_null(self):
        # Kolom NOT NULL: tidak dikirim boleh, dikirim null ditolak.
        for field in ("title", "pole_kind", "drawing_type"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{snake_to_camel(field)} cannot be null")
        return self


class DrawingCaseRead(CamelBaseModel):
    id: str
    request_id: str
    created_by_user_id: str
    owner_user_id: str
    calculation_case_id: str | None = None
    title: str
    case_label: str | None = None
    pole_kind: PoleKind
    drawing_type: DrawingType
    drawing_number: str | None = None
    part_number: str | None = None
    created_at: datetime
    updated_at: datetime