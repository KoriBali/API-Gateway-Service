import uuid
import enum
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    String,
    Numeric,
    Integer,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.database.models.identity import(
        User,
        Request,
    )

    from app.database.models.calculation_object import(
        DirectObject,
        DirectObjectResult,
        PoleResult,
    )

    from app.database.models.calculation_object import(
        StepPole,
        OverheadWire,
        OpeningPart,
        BasePlate,
        Foundation,
        Arm
    )

    from app.database.models.master import(
        PoleStandard,
        PoleStandardHeight,
        PoleCombination,
        RegionCode,
        DepartmentCode,
        AuthorCode
    )


# ===== Enums =====
class PoleFamily(str, enum.Enum):
    taper = "taper"
    straight = "straight"


class GroundPosition(str, enum.Enum):
    embedment = "embedment"
    on_GL = "on_GL"
    upper_GL = "upper_GL"
    under_GL = "under_GL"


class StatusCalculationRun(str, enum.Enum):
    ok = "ok"
    ng = "ng"



# ===== Calculation Case =====
class CalculationCase(Base):
    __tablename__ = "calculation_cases"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    request_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('requests.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    owner_user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('users.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    pole_standard_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey('pole_standards.id', ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True
    )

    pole_standard_height_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey('pole_standard_heights.id', ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True
    )

    pole_combination_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey('pole_combinations.id', ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True
    )

    pole_family: Mapped[PoleFamily | None] = mapped_column(
        Enum(PoleFamily),
        nullable=True
    )

    ground_position: Mapped[GroundPosition | None] = mapped_column(
        Enum(GroundPosition),
        nullable=True
    )

    lowest_height: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    embedment_length: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    overdesign_factor: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    title: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Parent
    conditions: Mapped[list["Condition"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    calculation_runs: Mapped[list["CalculationRun"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    direct_objects: Mapped[list["DirectObject"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    step_poles: Mapped[list["StepPole"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    arms: Mapped[list["Arm"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    overhead_wires: Mapped[list["OverheadWire"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    base_plates: Mapped[list["BasePlate"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    opening_parts: Mapped[list["OpeningPart"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    foundations: Mapped[list["Foundation"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    reports: Mapped[list["Report"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    # Child
    request: Mapped["Request"] = relationship(
        back_populates="calculation_cases"
    )

    owner_user: Mapped["User"] = relationship(
        back_populates="calculation_cases"
    )

    pole_standard: Mapped["PoleStandard | None"] = relationship(
        back_populates="calculation_cases"
    )

    pole_standard_height: Mapped["PoleStandardHeight | None"] = relationship(
        back_populates="calculation_cases"
    )

    pole_combination: Mapped["PoleCombination | None"] = relationship(
        back_populates="calculation_cases"
    )


# ===== Condition =====
class Condition(Base):
    __tablename__ = "conditions"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    calculation_case_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    design_standard_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('design_standards.id', ondelete="RESTRICT", onupdate="CASCADE")
    )

    wind_speed: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    air_density: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    # Child
    calculation_case: Mapped["CalculationCase"] = relationship(
        back_populates="conditions"
    )



# ===== Calculation Run =====
class CalculationRun(Base):
    __tablename__ = "calculation_runs"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    calculation_case_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    status: Mapped[StatusCalculationRun] = mapped_column(
        Enum(StatusCalculationRun),
        nullable=False
    )

    input_snapshot: Mapped[dict | None] = mapped_column(JSONB)

    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # Child
    calculation_case: Mapped["CalculationCase"] = relationship(
        back_populates="calculation_runs"
    )

    # Parent
    calculation_results: Mapped[list["CalculationResult"]] = relationship(
        back_populates="calculation_run",
        cascade="all, delete-orphan",
        passive_deletes=True
    )



# ===== Calculation Result =====
class CalculationResult(Base):
    __tablename__ = "calculation_results"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    calculation_run_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('calculation_runs.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    total_moment: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    total_windload: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    status: Mapped[StatusCalculationRun] = mapped_column(
        Enum(StatusCalculationRun),
        nullable=False
    )

    # Child
    calculation_run: Mapped["CalculationRun"] = relationship(
        back_populates="calculation_results"
    )

    # Parent
    pole_results: Mapped[list["PoleResult"]] = relationship(
        back_populates="calculation_result",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    direct_object_results: Mapped[list["DirectObjectResult"]] = relationship(
        back_populates="calculation_result",
        cascade="all, delete-orphan",
        passive_deletes=True
    )




# ===== Reports =====
class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    calculation_case_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    region_code_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('region_codes.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    department_code_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey('department_codes.id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True
    )

    author_code_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey('author_codes.id', ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True
    )

    report_number: Mapped[str] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    design_request_management_no: Mapped[str] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    report_title_1: Mapped[str] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    report_title_2: Mapped[str | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    report_title_3: Mapped[str | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )    

    # Child
    calculation_case: Mapped["CalculationCase"] = relationship(
        back_populates="reports"
    )

    region_code: Mapped["RegionCode"] = relationship(
        back_populates="reports"
    )

    department_code: Mapped["DepartmentCode"] = relationship(
        back_populates="reports"
    )

    author_code: Mapped["AuthorCode"] = relationship(
        back_populates="reports"
    )