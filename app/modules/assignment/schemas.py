from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import Field, model_validator

from app.utils.base_schema import CamelBaseModel
from app.database.models.identity import UserRole
from app.database.models.workflow import AssignmentStatus, WorkType


# Jam desimal, cocok dengan work_hours.hours numeric(5,2). Satu baris = satu hari kerja.
Hours = Annotated[Decimal, Field(gt=0, le=24, max_digits=4, decimal_places=2)]



# ===== Input =====
class AssignmentCreate(CamelBaseModel):
    assignee_user_id: str = Field(min_length=1)
    work_type: WorkType



class WorkHourCreate(CamelBaseModel):
    hours: Hours
    work_date: date
    # Putaran revisi tempat jam ini dibukukan. Kosong = di luar putaran revisi.
    revision_round_id: str | None = Field(default=None, min_length=1)



class WorkHourUpdate(CamelBaseModel):
    hours: Hours | None = None
    work_date: date | None = None
    # null eksplisit = keluarkan dari putaran revisi.
    revision_round_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _not_null(self):
        for field in ("hours", "work_date"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{type(self).model_fields[field].alias or field} cannot be null")
        return self



# ===== Output =====
class AssigneeRead(CamelBaseModel):
    id: str
    username: str
    full_name: str
    role: UserRole



class AssignmentRead(CamelBaseModel):
    id: str
    request_id: str
    assignee_user_id: str
    assignee: AssigneeRead
    assigned_by_user_id: str
    work_type: WorkType
    assignment_status: AssignmentStatus
    assigned_at: datetime
    released_at: datetime | None = None
    released_by_user_id: str | None = None
    # Jumlah jam di assignment ini. Hanya diisi GET daftar assignment; respons tambah/lepas null.
    total_hours: Decimal | None = None



class WorkHourRead(CamelBaseModel):
    id: str
    request_assignment_id: str
    revision_round_id: str | None = None
    hours: Decimal
    work_date: date



class WorkTypeHours(CamelBaseModel):
    work_type: WorkType
    total_hours: Decimal



class WorkHourSummaryRead(CamelBaseModel):
    """Ringkasan man-hour satu request, dipisah per work type seperti 工数 di cover YP."""
    total_hours: Decimal
    by_work_type: list[WorkTypeHours]
