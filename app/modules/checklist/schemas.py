from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from app.utils.base_schema import CamelBaseModel, snake_to_camel
from app.database.models.workflow import ChecklistItemStatus, WorkType


# Teks langkah dan butir: spasi di tepi dibuang, string kosong ditolak.
ChecklistText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
NoteText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]



# ===== Daftar induk (master) =====
class MasterItemCreate(CamelBaseModel):
    work_type: WorkType
    step: ChecklistText
    item: ChecklistText
    sort_order: int = Field(default=0, ge=0)


class MasterItemUpdate(CamelBaseModel):
    # work_type tidak bisa diubah: item drawing yang menjadi calculation adalah item baru.
    step: ChecklistText | None = None
    item: ChecklistText | None = None
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @model_validator(mode="after")
    def _not_null(self):
        for field in ("step", "item", "sort_order", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{snake_to_camel(field)} cannot be null")
        return self


class MasterItemRead(CamelBaseModel):
    id: str
    work_type: WorkType
    step: str
    item: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime



# ===== Checklist per siklus submit =====
class ChecklistItemUpdate(CamelBaseModel):
    item_status: ChecklistItemStatus | None = None
    start_at: datetime | None = None
    finish_at: datetime | None = None
    # Boleh diisi manual bila jam mulai tidak tercatat
    duration_minutes: int | None = Field(default=None, ge=0, le=100000)
    notes: NoteText | None = None

    @model_validator(mode="after")
    def _not_null(self):
        if "item_status" in self.model_fields_set and self.item_status is None:
            raise ValueError("itemStatus cannot be null")
        for field in ("start_at", "finish_at"):
            value = getattr(self, field)
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{snake_to_camel(field)} must include a timezone offset")
        return self


class ChecklistItemRead(CamelBaseModel):
    id: str
    nc_checklist_id: str
    source_master_id: str | None = None
    work_type: WorkType
    step: str
    item: str
    sort_order: int
    item_status: ChecklistItemStatus
    reviewed_by: str | None = None
    start_at: datetime | None = None
    finish_at: datetime | None = None
    duration_minutes: int | None = None
    notes: str | None = None


class ChecklistRead(CamelBaseModel):
    id: str
    request_id: str
    # Putaran asal Jepang yang memulai siklus ini. Kosong = siklus pertama.
    revision_round_id: str | None = None
    # True = checklist siklus submit berjalan, satu-satunya yang bisa diisi.
    is_current: bool
    pending_count: int
    # Tidak ada item pending lagi
    is_complete: bool
    items: list[ChecklistItemRead]